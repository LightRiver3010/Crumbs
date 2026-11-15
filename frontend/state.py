"""Keep user edits when conditional tabs/routes omit their widgets."""
import streamlit as st
CONTROL_KEYS={"ordering_habit","insight_orders","delivery_meals","meal_swaps",
              "meal_plan","period_start","period_end","period_confirmed","usual_weekly",
              "comparison_restaurant","comparison_category","comparison_meal",
              "landing_source","landing_search","landing_restaurant",
              "landing_category","landing_comparable","landing_meal",
              "same_food_item","same_restaurant","same_provider","same_quantity"}
PREFIXES=("review_","confirm_","apply_year_","date_year_","branch_","platform_","match_","qty_")

def preserve_controls(savings_only=False):
    for key in list(st.session_state):
        allowed = key in CONTROL_KEYS or key.startswith(PREFIXES)
        if savings_only:
            allowed = key in {"delivery_meals", "meal_swaps", "meal_plan",
                             "same_food_item", "same_restaurant", "same_provider", "same_quantity"} or key.startswith(("branch_", "platform_", "match_", "qty_"))
        if allowed:
            st.session_state[key]=st.session_state[key]
