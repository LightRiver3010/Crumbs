import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from benchmark_data.catalog import identify, validate_inventory, FILE_TYPES
from benchmark_data.organize import organize
from benchmark_data.s3_source import discover
from benchmark_data.warehouse import load_file

class ImportTests(unittest.TestCase):
    def test_naming_and_year(self):
        file=identify("reference/2025/expd251.csv",2025)
        self.assertEqual(file.table_name,"expd_2025_q1")
        with self.assertRaises(ValueError): identify("expd241.csv",2025)
        with self.assertRaises(ValueError): identify("expd255.csv",2025)
    def test_inventory(self):
        files=[identify(f"{kind}25{q}.csv",2025) for kind in FILE_TYPES for q in range(1,5)]
        self.assertEqual(validate_inventory(files),[])
        with self.assertRaises(ValueError): validate_inventory(files[:-1])
        with self.assertRaises(ValueError): validate_inventory(files+[files[0]])
    def test_pagination(self):
        client=MagicMock()
        client.get_paginator.return_value.paginate.return_value=[{"Contents":[{"Key":"prefix/fmld251.csv"}]},{"Contents":[{"Key":"prefix/memd251.csv"}]}]
        files,missing=discover(client,"bucket","prefix",2025,True)
        self.assertEqual(len(files),2)
        self.assertEqual(len(missing),18)
    def test_lossless_raw_values(self):
        with tempfile.TemporaryDirectory() as temp:
            src=Path(temp)/"expd251.csv";out=Path(temp)/"records.jsonl"
            src.write_text("NEWID,UCC,COST,EXPNMO_\n06004781,010210,4.54581,\n06004781,010210,4.54581,\n")
            record=organize(identify(src.name,2025),src,out,"s3://bucket/key")
            rows=[json.loads(x) for x in out.read_text().splitlines()]
            self.assertEqual(record["row_count"],2)
            self.assertEqual(rows[0]["NEWID"],"06004781")
            self.assertEqual(rows[0]["COST"],"4.54581")
            self.assertEqual(rows[0]["EXPNMO_"],"")
            self.assertEqual(rows[1]["bls_source_row"],2)
    def test_malformed_csv_never_published(self):
        with tempfile.TemporaryDirectory() as temp:
            src=Path(temp)/"expd251.csv";out=Path(temp)/"records.jsonl"
            src.write_text("NEWID,UCC,COST\n001,123\n")
            with self.assertRaises(ValueError): organize(identify(src.name,2025),src,out,"uri")
            self.assertFalse(out.exists())
    def test_duplicate_family_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            src=Path(temp)/"fmld251.csv"
            src.write_text("NEWID,FINLWT21,FAM_SIZE\n001,4,1\n001,4,1\n")
            with self.assertRaises(ValueError): organize(identify(src.name,2025),src,Path(temp)/"out.jsonl","uri")
    def test_load_job_no_queries_and_no_append(self):
        with tempfile.TemporaryDirectory() as temp:
            src=Path(temp)/"records.jsonl";src.write_text("{}\n")
            client=MagicMock()
            client.create_dataset.return_value.location="US"
            client.get_table.return_value.num_rows=1
            record={"columns":["NEWID","COST"],"row_count":1,"organized_jsonl":str(src)}
            result=load_file(identify("expd251.csv",2025),record,client=client)
            config=client.load_table_from_file.call_args.kwargs["job_config"]
            self.assertEqual(config.write_disposition,"WRITE_TRUNCATE")
            self.assertEqual(config.schema[0].field_type,"STRING")
            client.query.assert_not_called()
            self.assertTrue(result["table"].endswith("expd_2025_q1"))

if __name__ == "__main__":
    unittest.main()
