import unittest
from io import BytesIO
from unittest.mock import patch, MagicMock
from PIL import Image
from pydantic import ValidationError
from receipt_extraction.schemas import Extraction, Order
from receipt_extraction.images import normalize_image
from receipt_extraction.deduplication import order_id
from receipt_extraction import pipeline, repository, gemini_client

class ReceiptTests(unittest.TestCase):
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-placeholder"})
    @patch.object(gemini_client.genai, "Client")
    def test_gemini_response_validated(self, client):
        client.return_value.__enter__.return_value.models.generate_content.return_value.text = '{"orders":[{"restaurant":"Test","total_cents":1234}],"warnings":[]}'
        result = gemini_client.extract_image(b"png")
        self.assertEqual(result.orders[0].total_cents, 1234)
        config = client.return_value.__enter__.return_value.models.generate_content.call_args.kwargs["config"]
        self.assertIsNone(config.response_json_schema)
        self.assertIsNotNone(config.response_schema)
        self.assertNotIn("additionalProperties", str(gemini_client.api_schema()))
        self.assertEqual(Extraction.model_json_schema()["additionalProperties"], False)
    def test_oversize_rejected(self):
        with self.assertRaises(ValueError):
            normalize_image(b"x" * (10 * 1024 * 1024 + 1))
    def test_depleted_credit_message(self):
        error = Exception()
        error.code = 402
        error.message = "Your prepayment credits are depleted."
        message = gemini_client.extraction_error_message(error)
        self.assertIn("prepayment credits are depleted", message)
        self.assertIn("billing", message)

    def test_unavailable_model_message(self):
        error = Exception()
        error.code = 404
        message = gemini_client.extraction_error_message(error)
        self.assertIn("model is unavailable", message)
        self.assertIn("GEMINI_MODEL", message)

    def test_spend_cap_message(self):
        error = Exception()
        error.code = 403
        error.message = "Spend cap breached for project: projects/test"
        message = gemini_client.extraction_error_message(error)
        self.assertIn("spending cap", message)
        self.assertNotIn("denied access", message)

    def test_disabled_api_message(self):
        error = Exception()
        error.code = 403
        error.message = "Gemini API has not been used or it is disabled. secret-placeholder"
        message = gemini_client.extraction_error_message(error)
        self.assertIn("Enable", message)
        self.assertNotIn("secret-placeholder", message)

    def test_negative_money_rejected(self):
        with self.assertRaises(ValidationError):
            Order(total_cents=-1)
    def test_missing_stays_null(self):
        self.assertIsNone(Order().total_cents)
    def test_invalid_date_rejected(self):
        with self.assertRaises(ValidationError):
            Order(order_date="2026-02-30")
    def test_nonimage_rejected(self):
        with self.assertRaises(Exception):
            normalize_image(b"not an image")
    def test_convert_jpeg(self):
        data=BytesIO()
        Image.new("RGB",(20,20)).save(data,format="JPEG")
        self.assertTrue(normalize_image(data.getvalue()).startswith(b"\x89PNG"))
    def test_duplicate_reference_across_uploads(self):
        order=Order(provider="doordash",order_reference="123")
        self.assertEqual(order_id("s","a",0,order),order_id("s","b",2,order))
        self.assertNotEqual(order_id("s","a",0,order),order_id("t","a",0,order))
    def test_no_reference_keeps_distinct_orders(self):
        self.assertNotEqual(order_id("s","a",0,Order()),order_id("s","a",1,Order()))
    @patch.object(pipeline,"extract_image")
    @patch.object(pipeline,"upload_image",return_value="s3://bucket/key")
    @patch.object(pipeline,"normalize_image",return_value=b"png")
    def test_prepare_does_not_save(self,normalize,upload,extract):
        extract.return_value=Extraction(orders=[Order(restaurant="Test")])
        identifier,uri,result=pipeline.prepare(b"input","session")
        upload.assert_called_once_with(b"png","session",identifier)
        extract.assert_called_once_with(b"png")
        self.assertEqual(uri,"s3://bucket/key")
    @patch.object(repository,"get_client")
    def test_save_parameterized(self,client):
        repository.save("session","upload","s3://bucket/key",Extraction(orders=[Order(restaurant="O'Reilly")]))
        args,kwargs=client.return_value.query.call_args
        self.assertNotIn("O'Reilly",args[0])
        self.assertIn("BEGIN TRANSACTION",args[0])
        client.return_value.query.return_value.result.assert_called_once()
    @patch.object(repository,"get_client")
    def test_duplicate_reference_rejected_before_write(self,client):
        order=Order(provider="test",order_reference="123")
        with self.assertRaises(ValueError):
            repository.save("s","u","uri",Extraction(orders=[order,order]))
        client.assert_not_called()

if __name__ == "__main__":
    unittest.main()
