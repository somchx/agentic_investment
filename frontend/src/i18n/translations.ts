// Lightweight, dependency-free i18n dictionaries.
// Keep keys flat and short. Add new keys to BOTH `en` and `th`.

export const en = {
  // App shell / layout
  app_title: "ReasonCheck",
  app_subtitle: "Revalidate Every Reason.",
  nav_dashboard: "Dashboard",
  nav_screener: "Screener",
  nav_portfolio: "Portfolio",
  nav_profiles: "Profiles",
  nav_agent: "Agent",
  nav_logout: "Log out",
  nav_main_label: "Main",
  nav_section_main: "Main",
  nav_section_tools: "Tools",
  sidebar_expand: "Expand sidebar",
  sidebar_collapse: "Collapse sidebar",
  sidebar_open: "Open menu",
  sidebar_close: "Close menu",
  lang_toggle_en: "EN",
  lang_toggle_th: "TH",
  theme_toggle_light: "Light mode",
  theme_toggle_dark: "Dark mode",
  notifications_title: "Notifications",
  notifications_check_now: "Check now",
  notifications_mark_all_read: "Mark all read",
  notifications_empty: "No notifications yet -- you'll see one here if a reason's status changes.",

  // Auth page
  auth_app_title: "ReasonCheck",
  auth_app_description: "Evidence-grounded revalidation of your investment theses.",
  auth_tagline: "Evidence-grounded, point-in-time revalidation",
  auth_feature_evidence_title: "Point-in-time evidence",
  auth_feature_evidence_desc: "Every check is grounded in SEC filings as they stood at the time — never hindsight.",
  auth_feature_screening_title: "Mechanical screening",
  auth_feature_screening_desc: "Runs your own rules against the data. No AI stock-picking, no recommendations.",
  auth_feature_thesis_title: "Track your thesis",
  auth_feature_thesis_desc: "See whether the reason you bought still holds, backed by the latest filed evidence.",
  auth_footer_tagline: "Not investment advice. Mechanical, evidence-based checks on your own criteria only.",
  auth_login_tab: "Log in",
  auth_register_tab: "Register",
  auth_field_email: "Email",
  auth_field_password: "Password",
  auth_password_hint: "Use at least 8 characters.",
  auth_submit_login: "Log in",
  auth_submit_register: "Create account",
  auth_submit_pending: "Please wait...",
  auth_error_default: "Authentication failed. Please try again.",

  // Dashboard page
  dashboard_select_company: "Select a company to see its evidence report.",
  dashboard_report_subtitle:
    "Each card below is one of your reasons for holding or watching this company, checked against the latest filed evidence.",
  dashboard_report_loading: "Loading report...",
  dashboard_report_error: "Could not load the evidence report for {ticker}.",
  dashboard_no_reasons: "No reasons yet for {ticker}. Add a built-in reason from the backend or define a custom one below.",

  // Company list
  company_search_placeholder: "Search companies...",
  company_list_loading: "Loading companies...",
  company_list_error: "Could not load companies.",
  company_list_empty: "No companies match.",

  // Reason report card
  reason_card_no_value: "no data yet",
  reason_card_as_of: "as of {date}",
  reason_card_was: "was {status}",
  reason_card_delete_aria: "Delete custom reason",

  // Create reason form
  create_reason_title: "Define a custom reason",
  create_reason_description: "Pick an XBRL metric reported by {ticker} — never free text — and the rule it must keep satisfying.",
  create_reason_field_description: "Description",
  create_reason_description_placeholder: "e.g. Gross margin must stay above 40%",
  create_reason_field_metric: "Metric",
  create_reason_metric_loading: "Loading metrics...",
  create_reason_metric_placeholder: "Choose a metric",
  create_reason_field_kind: "Kind",
  create_reason_field_comparison: "Comparison",
  create_reason_field_denominator: "Denominator metric",
  create_reason_denominator_placeholder: "Choose the denominator metric",
  create_reason_field_threshold: "Threshold",
  create_reason_threshold_placeholder: "e.g. 0.4",
  create_reason_submit: "Add reason",
  create_reason_submit_pending: "Saving...",
  create_reason_kind_value: "Raw value",
  create_reason_kind_ratio: "Ratio of two metrics",
  create_reason_kind_growth: "Growth vs. prior period",
  create_reason_comparison_gt: "greater than (>)",
  create_reason_comparison_gte: "greater than or equal (>=)",
  create_reason_comparison_lt: "less than (<)",
  create_reason_comparison_lte: "less than or equal (<=)",
  create_reason_comparison_eq: "equal to (==)",
  create_reason_comparison_ne: "not equal to (!=)",
  create_reason_err_pick_metric: "Pick a metric from the list.",
  create_reason_err_description: "Give this reason a short description.",
  create_reason_err_threshold: "Threshold must be a number.",
  create_reason_err_denominator: "Pick a denominator metric for a ratio/margin reason.",
  create_reason_err_default: "Could not create this reason.",
  create_reason_success: "Reason saved — see it in the cards above.",

  // Record purchase form
  record_purchase_title: "Record a purchase",
  record_purchase_description:
    "Link this position to one of your reasons — the backend freezes that reason's status at purchase time so you can compare it against the live status later.",
  record_purchase_field_quantity: "Quantity",
  record_purchase_field_price: "Purchase price",
  record_purchase_field_date: "Purchase date",
  record_purchase_field_reason: "Reason (optional)",
  record_purchase_reason_placeholder: "Attach a reason for this purchase",
  record_purchase_submit: "Record purchase",
  record_purchase_submit_pending: "Saving...",
  record_purchase_success: "Purchase recorded.",
  record_purchase_err_quantity: "Quantity must be a positive number.",
  record_purchase_err_price: "Purchase price must be a positive number.",
  record_purchase_err_default: "Could not record this purchase.",

  // Ask agent panel
  ask_agent_title: "Ask the agent",
  ask_agent_description:
    "Free-form questions about {ticker} are answered by an LLM with tool access to the evidence data. This calls a paid API — nothing is sent until you confirm.",
  ask_agent_question_placeholder: "e.g. Has {ticker}'s revenue growth reason weakened recently, and why?",
  ask_agent_button: "Ask the agent (uses a paid LLM call)",
  ask_agent_cost: "Cost: ${cost}",
  ask_agent_tool_calls: "{count} tool call",
  ask_agent_tool_calls_plural: "{count} tool calls",
  ask_agent_err_default: "The agent call failed.",
  ask_agent_dialog_title: "This will call a paid LLM",
  ask_agent_dialog_description:
    "Asking the agent about {ticker} sends your question to a language model with tool access and will incur a real API cost. Continue?",
  ask_agent_dialog_confirm: "Ask anyway",

  // Agent page (standalone chat)
  agent_page_title: "Ask the Agent",
  agent_page_subtitle:
    "Chat with an LLM that has tool access to your evidence data -- one company, or everything you hold. Each message you send is a paid API call.",
  agent_ticker_label: "Company",
  agent_ticker_placeholder: "Choose a company",
  agent_new_chat: "New chat",
  chat_history_toggle_aria: "Toggle chat history",
  chat_history_title: "Chats",
  chat_history_empty: "No past chats yet.",
  chat_history_delete_aria: "Delete this chat",
  chat_copy_aria: "Copy response",
  chat_copied: "Copied",
  chat_edit_aria: "Edit this question",
  chat_regenerate_aria: "Regenerate response",
  agent_empty_heading: "Ask about {ticker}",
  agent_empty_subtitle:
    "Ask a free-form question about {ticker}'s reasons and filed evidence. The agent can look up reason status, metrics, and filing context before answering.",
  agent_suggestion_1: "Has {ticker}'s revenue growth reason weakened recently, and why?",
  agent_suggestion_2: "Why is {ticker}'s operating margin reason marked as Broken?",
  agent_suggestion_3: "What does {ticker}'s latest 10-Q say about their debt growth?",
  agent_suggestion_4: "Summarize the current status of every reason for {ticker}.",
  agent_input_placeholder: "Ask a question about {ticker}...",
  agent_send_aria: "Send message",
  agent_select_company_first: "Choose a company above to start a conversation.",
  agent_dialog_title: "This will start a paid conversation",
  agent_dialog_description:
    "Starting a conversation with the agent about {ticker} calls a paid LLM API for every message you send. Continue?",
  agent_dialog_confirm: "Start conversation",
  agent_tool_calls_detail: "Tools used: {tools}",
  agent_thinking: "Thinking...",
  agent_portfolio_option_label: "My Portfolio (all holdings)",
  agent_portfolio_empty_heading: "Ask about your portfolio",
  agent_portfolio_empty_subtitle:
    "Ask a free-form question across everything you hold. The agent can check any position's reason status before answering -- it will never suggest what to buy or sell.",
  agent_portfolio_suggestion_1: "How is my portfolio doing right now?",
  agent_portfolio_suggestion_2: "Which of my holdings look risky or concerning?",
  agent_portfolio_suggestion_3: "Which position is closest to breaking its reason?",
  agent_portfolio_suggestion_4: "What's changed since I bought each position?",
  agent_portfolio_input_placeholder: "Ask a question about your portfolio...",
  agent_portfolio_dialog_description:
    "Starting a conversation with the agent about your portfolio calls a paid LLM API for every message you send. Continue?",

  // Cost confirm dialog (defaults)
  cost_confirm_cancel: "Cancel",
  cost_confirm_pending: "Working...",
  cost_confirm_default_confirm: "Yes, spend the money",

  // Screener page
  screener_title: "Screener",
  screener_intro:
    "The screener mechanically checks every covered company against the rule(s) you defined — it is not investment advice and it does not recommend anything. It reuses the exact same evidence check as the dashboard report, with zero AI involved.",
  screener_choose_rules_title: "Choose one or more rules",
  screener_choose_rules_description:
    "Pick any of your own reasons. Each selected rule gets its own status column below — this shows every company side by side, it does not filter companies out.",
  screener_loading_reasons: "Loading your reasons...",
  screener_no_reasons: "No reasons yet — define one from a company's dashboard page first.",
  screener_ticker_any: "any",
  screener_run: "Run screen",
  screener_run_multi: "Run screen ({count} rules)",
  screener_running: "Running...",
  screener_disclaimer:
    "Each column below shows whether a company currently satisfies that rule. This is a side-by-side filter on your own criteria, not a recommendation to buy or sell anything.",
  screener_error: "Could not run the screen.",
  screener_table_company: "Company",
  screener_table_na: "n/a",

  // Portfolio page
  portfolio_title: "Portfolio",
  portfolio_intro:
    "Every position you've recorded, grouped by company, with the reason you bought it for frozen at purchase time next to that reason's current status.",
  portfolio_ask_agent: "Ask the agent",
  portfolio_loading: "Loading portfolio...",
  portfolio_error: "Could not load your portfolio.",
  portfolio_empty: "No positions yet. Record a purchase from the dashboard to see it here.",
  portfolio_position_summary: "{quantity} sh @ ${price} on {date}",
  portfolio_bought_for: "Bought for: {description} (was {status} at purchase)",
  portfolio_no_reason: "No reason attached to this purchase.",
  portfolio_value_at_purchase: "At purchase:",
  portfolio_value_now: "Now:",
  portfolio_status_unknown: "Unknown",
  portfolio_status_still_true: "Still true",
  portfolio_status_broken: "No longer true",
  portfolio_delete_position_aria: "Delete position",

  // Profiles page
  profiles_title: "Investor profiles",
  profiles_intro:
    "Profiles describe your risk tolerance and objectives. They're used by the paid personalization feature on the dashboard — they don't do anything on their own.",
  profiles_new_title: "New profile",
  profiles_new_description: "Add a reusable investor profile.",
  profiles_field_name: "Name",
  profiles_field_risk: "Risk tolerance",
  profiles_risk_placeholder: "e.g. moderate",
  profiles_field_horizon: "Investment horizon",
  profiles_horizon_placeholder: "e.g. 5-10 years",
  profiles_field_size: "Position size (%)",
  profiles_field_objective: "Objective",
  profiles_objective_placeholder: "e.g. long-term capital appreciation",
  profiles_submit: "Add profile",
  profiles_submit_pending: "Saving...",
  profiles_loading: "Loading profiles...",
  profiles_error: "Could not load profiles.",
  profiles_err_name: "Give the profile a name.",
  profiles_err_size: "Position size % must be a number.",
  profiles_err_default: "Could not create this profile.",
  profiles_delete_aria: "Delete profile",
  profiles_card_risk: "Risk: {value}",
  profiles_card_horizon: "Horizon: {value}",
  profiles_card_size: "Position size: {value}%",
  profiles_card_objective: "Objective: {value}",

  // Status badge
  status_supported: "Supported",
  status_weakened: "Weakened",
  status_broken: "Broken",
  status_not_enough_data: "Not enough data",
} as const

export const th: Record<keyof typeof en, string> = {
  // App shell / layout
  app_title: "ReasonCheck",
  app_subtitle: "ทบทวนทุกเหตุผลอีกครั้ง",
  nav_dashboard: "แดชบอร์ด",
  nav_screener: "ตัวคัดกรอง",
  nav_portfolio: "พอร์ต",
  nav_profiles: "โปรไฟล์",
  nav_agent: "เอเจนต์",
  nav_logout: "ออกจากระบบ",
  nav_main_label: "หลัก",
  nav_section_main: "หลัก",
  nav_section_tools: "เครื่องมือ",
  sidebar_expand: "ขยายแถบเมนู",
  sidebar_collapse: "ย่อแถบเมนู",
  sidebar_open: "เปิดเมนู",
  sidebar_close: "ปิดเมนู",
  lang_toggle_en: "EN",
  lang_toggle_th: "TH",
  theme_toggle_light: "โหมดสว่าง",
  theme_toggle_dark: "โหมดมืด",
  notifications_title: "การแจ้งเตือน",
  notifications_check_now: "เช็คตอนนี้เลย",
  notifications_mark_all_read: "อ่านทั้งหมดแล้ว",
  notifications_empty: "ยังไม่มีการแจ้งเตือน — จะขึ้นตรงนี้ถ้าสถานะของเหตุผลเปลี่ยนไป",

  // Auth page
  auth_app_title: "ReasonCheck",
  auth_app_description: "ตรวจสอบสมมติฐานการลงทุนของคุณซ้ำโดยอ้างอิงหลักฐาน",
  auth_tagline: "ตรวจสอบซ้ำโดยอ้างอิงหลักฐาน ณ ช่วงเวลานั้น ๆ",
  auth_feature_evidence_title: "หลักฐาน ณ เวลาที่เกิดขึ้นจริง",
  auth_feature_evidence_desc: "ทุกการตรวจสอบอ้างอิงจากเอกสารยื่นต่อ SEC ตามช่วงเวลานั้น ๆ ไม่ใช่การมองย้อนหลัง",
  auth_feature_screening_title: "การคัดกรองแบบอัตโนมัติ",
  auth_feature_screening_desc: "รันตามเงื่อนไขของคุณเองกับข้อมูลจริง ไม่มี AI เลือกหุ้นและไม่มีคำแนะนำใด ๆ",
  auth_feature_thesis_title: "ติดตามสมมติฐานของคุณ",
  auth_feature_thesis_desc: "ดูว่าเหตุผลที่คุณซื้อยังคงเป็นจริงอยู่หรือไม่ อ้างอิงจากหลักฐานล่าสุดที่ยื่นไว้",
  auth_footer_tagline: "ไม่ใช่คำแนะนำการลงทุน เป็นเพียงการตรวจสอบอัตโนมัติตามเกณฑ์ของคุณเองโดยอ้างอิงหลักฐานเท่านั้น",
  auth_login_tab: "เข้าสู่ระบบ",
  auth_register_tab: "สมัครสมาชิก",
  auth_field_email: "อีเมล",
  auth_field_password: "รหัสผ่าน",
  auth_password_hint: "ใช้อย่างน้อย 8 ตัวอักษร",
  auth_submit_login: "เข้าสู่ระบบ",
  auth_submit_register: "สร้างบัญชี",
  auth_submit_pending: "กรุณารอสักครู่...",
  auth_error_default: "การยืนยันตัวตนล้มเหลว กรุณาลองใหม่อีกครั้ง",

  // Dashboard page
  dashboard_select_company: "เลือกบริษัทเพื่อดูรายงานหลักฐาน",
  dashboard_report_subtitle:
    "การ์ดแต่ละใบด้านล่างคือเหตุผลหนึ่งของคุณในการถือหรือติดตามบริษัทนี้ ซึ่งถูกตรวจสอบกับหลักฐานล่าสุดที่ยื่นไว้",
  dashboard_report_loading: "กำลังโหลดรายงาน...",
  dashboard_report_error: "ไม่สามารถโหลดรายงานหลักฐานของ {ticker} ได้",
  dashboard_no_reasons: "ยังไม่มีเหตุผลสำหรับ {ticker} เพิ่มเหตุผลสำเร็จรูปจากระบบหลังบ้าน หรือกำหนดเหตุผลของคุณเองด้านล่าง",

  // Company list
  company_search_placeholder: "ค้นหาบริษัท...",
  company_list_loading: "กำลังโหลดรายชื่อบริษัท...",
  company_list_error: "ไม่สามารถโหลดรายชื่อบริษัทได้",
  company_list_empty: "ไม่พบบริษัทที่ตรงกัน",

  // Reason report card
  reason_card_no_value: "ยังไม่มีข้อมูล",
  reason_card_as_of: "ข้อมูล ณ วันที่ {date}",
  reason_card_was: "ก่อนหน้านี้คือ {status}",
  reason_card_delete_aria: "ลบเหตุผลที่กำหนดเอง",

  // Create reason form
  create_reason_title: "กำหนดเหตุผลของคุณเอง",
  create_reason_description: "เลือกตัวชี้วัด XBRL ที่ {ticker} รายงานไว้ — ห้ามพิมพ์เอง — พร้อมเงื่อนไขที่ต้องเป็นจริงอยู่เสมอ",
  create_reason_field_description: "คำอธิบาย",
  create_reason_description_placeholder: "เช่น อัตรากำไรขั้นต้นต้องสูงกว่า 40%",
  create_reason_field_metric: "ตัวชี้วัด",
  create_reason_metric_loading: "กำลังโหลดตัวชี้วัด...",
  create_reason_metric_placeholder: "เลือกตัวชี้วัด",
  create_reason_field_kind: "ประเภท",
  create_reason_field_comparison: "การเปรียบเทียบ",
  create_reason_field_denominator: "ตัวชี้วัดตัวหาร",
  create_reason_denominator_placeholder: "เลือกตัวชี้วัดที่ใช้เป็นตัวหาร",
  create_reason_field_threshold: "เกณฑ์",
  create_reason_threshold_placeholder: "เช่น 0.4",
  create_reason_submit: "เพิ่มเหตุผล",
  create_reason_submit_pending: "กำลังบันทึก...",
  create_reason_kind_value: "ค่าดิบ",
  create_reason_kind_ratio: "อัตราส่วนของสองตัวชี้วัด",
  create_reason_kind_growth: "การเติบโตเทียบกับงวดก่อนหน้า",
  create_reason_comparison_gt: "มากกว่า (>)",
  create_reason_comparison_gte: "มากกว่าหรือเท่ากับ (>=)",
  create_reason_comparison_lt: "น้อยกว่า (<)",
  create_reason_comparison_lte: "น้อยกว่าหรือเท่ากับ (<=)",
  create_reason_comparison_eq: "เท่ากับ (==)",
  create_reason_comparison_ne: "ไม่เท่ากับ (!=)",
  create_reason_err_pick_metric: "กรุณาเลือกตัวชี้วัดจากรายการ",
  create_reason_err_description: "กรุณาใส่คำอธิบายสั้น ๆ ให้เหตุผลนี้",
  create_reason_err_threshold: "เกณฑ์ต้องเป็นตัวเลข",
  create_reason_err_denominator: "กรุณาเลือกตัวชี้วัดตัวหารสำหรับเหตุผลแบบอัตราส่วน/มาร์จิ้น",
  create_reason_err_default: "ไม่สามารถสร้างเหตุผลนี้ได้",
  create_reason_success: "บันทึกเหตุผลแล้ว — ดูได้ในการ์ดด้านบน",

  // Record purchase form
  record_purchase_title: "บันทึกการซื้อ",
  record_purchase_description:
    "เชื่อมโยงสถานะการถือครองนี้กับเหตุผลของคุณ — ระบบหลังบ้านจะบันทึกสถานะของเหตุผลนั้น ณ เวลาที่ซื้อ เพื่อให้คุณเปรียบเทียบกับสถานะปัจจุบันได้ในภายหลัง",
  record_purchase_field_quantity: "จำนวนหน่วย",
  record_purchase_field_price: "ราคาที่ซื้อ",
  record_purchase_field_date: "วันที่ซื้อ",
  record_purchase_field_reason: "เหตุผล (ไม่บังคับ)",
  record_purchase_reason_placeholder: "แนบเหตุผลสำหรับการซื้อครั้งนี้",
  record_purchase_submit: "บันทึกการซื้อ",
  record_purchase_submit_pending: "กำลังบันทึก...",
  record_purchase_success: "บันทึกการซื้อเรียบร้อยแล้ว",
  record_purchase_err_quantity: "จำนวนหน่วยต้องเป็นตัวเลขที่มากกว่าศูนย์",
  record_purchase_err_price: "ราคาที่ซื้อต้องเป็นตัวเลขที่มากกว่าศูนย์",
  record_purchase_err_default: "ไม่สามารถบันทึกการซื้อนี้ได้",

  // Ask agent panel
  ask_agent_title: "ถามเอเจนต์",
  ask_agent_description:
    "คำถามปลายเปิดเกี่ยวกับ {ticker} จะได้รับคำตอบจาก LLM ที่เข้าถึงข้อมูลหลักฐานได้ การเรียกใช้นี้มีค่าใช้จ่ายจาก API — จะไม่มีการส่งข้อมูลจนกว่าคุณจะยืนยัน",
  ask_agent_question_placeholder: "เช่น เหตุผลเรื่องการเติบโตของรายได้ของ {ticker} อ่อนแรงลงเมื่อเร็ว ๆ นี้หรือไม่ เพราะอะไร?",
  ask_agent_button: "ถามเอเจนต์ (มีค่าใช้จ่ายจาก LLM)",
  ask_agent_cost: "ค่าใช้จ่าย: ${cost}",
  ask_agent_tool_calls: "{count} การเรียกใช้เครื่องมือ",
  ask_agent_tool_calls_plural: "{count} การเรียกใช้เครื่องมือ",
  ask_agent_err_default: "การเรียกเอเจนต์ล้มเหลว",
  ask_agent_dialog_title: "การกระทำนี้จะเรียกใช้ LLM ที่มีค่าใช้จ่าย",
  ask_agent_dialog_description:
    "การถามเอเจนต์เกี่ยวกับ {ticker} จะส่งคำถามของคุณไปยังโมเดลภาษาที่เข้าถึงเครื่องมือได้ และจะมีค่าใช้จ่าย API จริงเกิดขึ้น ต้องการดำเนินการต่อหรือไม่?",
  ask_agent_dialog_confirm: "ยืนยันการถาม",

  // Agent page (standalone chat)
  agent_page_title: "ถามเอเจนต์",
  agent_page_subtitle: "สนทนากับ LLM ที่เข้าถึงข้อมูลหลักฐานได้ ทั้งของบริษัทเดียวหรือทุกสถานะที่คุณถืออยู่ ทุกข้อความที่คุณส่งมีค่าใช้จ่าย API จริง",
  agent_ticker_label: "บริษัท",
  agent_ticker_placeholder: "เลือกบริษัท",
  agent_new_chat: "เริ่มแชทใหม่",
  chat_history_toggle_aria: "แสดง/ซ่อนประวัติแชท",
  chat_history_title: "แชท",
  chat_history_empty: "ยังไม่มีแชทเก่า",
  chat_history_delete_aria: "ลบแชทนี้",
  chat_copy_aria: "คัดลอกคำตอบ",
  chat_copied: "คัดลอกแล้ว",
  chat_edit_aria: "แก้ไขคำถามนี้",
  chat_regenerate_aria: "ถามซ้ำอีกครั้ง",
  agent_empty_heading: "ถามเกี่ยวกับ {ticker}",
  agent_empty_subtitle:
    "ถามคำถามปลายเปิดเกี่ยวกับเหตุผลและหลักฐานที่ยื่นไว้ของ {ticker} เอเจนต์สามารถตรวจสอบสถานะเหตุผล ตัวชี้วัด และบริบทเอกสารก่อนตอบได้",
  agent_suggestion_1: "เหตุผลเรื่องการเติบโตของรายได้ของ {ticker} อ่อนแรงลงเมื่อเร็ว ๆ นี้หรือไม่ เพราะอะไร?",
  agent_suggestion_2: "ทำไมเหตุผลเรื่องอัตรากำไรจากการดำเนินงานของ {ticker} จึงถูกระบุว่าไม่เป็นจริงแล้ว?",
  agent_suggestion_3: "10-Q ล่าสุดของ {ticker} ระบุอะไรเกี่ยวกับการเติบโตของหนี้สิน?",
  agent_suggestion_4: "สรุปสถานะปัจจุบันของทุกเหตุผลของ {ticker}",
  agent_input_placeholder: "ถามคำถามเกี่ยวกับ {ticker}...",
  agent_send_aria: "ส่งข้อความ",
  agent_select_company_first: "เลือกบริษัทด้านบนเพื่อเริ่มการสนทนา",
  agent_dialog_title: "การกระทำนี้จะเริ่มการสนทนาแบบมีค่าใช้จ่าย",
  agent_dialog_description:
    "การเริ่มสนทนากับเอเจนต์เกี่ยวกับ {ticker} จะเรียกใช้ LLM ที่มีค่าใช้จ่ายทุกข้อความที่คุณส่ง ต้องการดำเนินการต่อหรือไม่?",
  agent_dialog_confirm: "เริ่มการสนทนา",
  agent_tool_calls_detail: "เครื่องมือที่ใช้: {tools}",
  agent_thinking: "กำลังคิด...",
  agent_portfolio_option_label: "พอร์ตของฉัน (ทุกสถานะที่ถือ)",
  agent_portfolio_empty_heading: "ถามเกี่ยวกับพอร์ตของคุณ",
  agent_portfolio_empty_subtitle:
    "ถามคำถามอิสระเกี่ยวกับทุกสถานะที่คุณถืออยู่ได้เลย เอเจนต์จะเช็คสถานะเหตุผลของแต่ละตัวก่อนตอบ — จะไม่แนะนำว่าควรซื้อหรือขายอะไรทั้งสิ้น",
  agent_portfolio_suggestion_1: "ตอนนี้พอร์ตของฉันเป็นอย่างไรบ้าง?",
  agent_portfolio_suggestion_2: "มีตัวไหนในพอร์ตที่น่าเป็นห่วงบ้าง?",
  agent_portfolio_suggestion_3: "ตัวไหนใกล้จะไม่เป็นจริงตามเหตุผลที่ตั้งไว้มากที่สุด?",
  agent_portfolio_suggestion_4: "มีอะไรเปลี่ยนไปบ้างตั้งแต่ฉันซื้อแต่ละตัว?",
  agent_portfolio_input_placeholder: "ถามคำถามเกี่ยวกับพอร์ตของคุณ...",
  agent_portfolio_dialog_description:
    "การเริ่มบทสนทนากับเอเจนต์เกี่ยวกับพอร์ตของคุณจะเรียกใช้ API แบบเสียค่าใช้จ่ายทุกข้อความที่คุณส่ง ดำเนินการต่อหรือไม่?",

  // Cost confirm dialog (defaults)
  cost_confirm_cancel: "ยกเลิก",
  cost_confirm_pending: "กำลังดำเนินการ...",
  cost_confirm_default_confirm: "ใช่ ยอมเสียค่าใช้จ่าย",

  // Screener page
  screener_title: "ตัวคัดกรอง",
  screener_intro:
    "ตัวคัดกรองนี้ตรวจสอบทุกบริษัทที่รวบรวมไว้กับเงื่อนไขที่คุณกำหนดเองโดยอัตโนมัติ — นี่ไม่ใช่คำแนะนำการลงทุนและไม่ได้แนะนำให้ทำสิ่งใดทั้งสิ้น โดยใช้การตรวจสอบหลักฐานชุดเดียวกับรายงานในแดชบอร์ด โดยไม่มี AI เข้ามาเกี่ยวข้องเลย",
  screener_choose_rules_title: "เลือกเงื่อนไขหนึ่งข้อขึ้นไป",
  screener_choose_rules_description:
    "เลือกเหตุผลใด ๆ ของคุณเอง แต่ละเงื่อนไขที่เลือกจะมีคอลัมน์สถานะของตัวเองด้านล่าง — แสดงทุกบริษัทเรียงเทียบกัน โดยไม่ได้กรองบริษัทออกไป",
  screener_loading_reasons: "กำลังโหลดเหตุผลของคุณ...",
  screener_no_reasons: "ยังไม่มีเหตุผล — กำหนดเหตุผลจากหน้าแดชบอร์ดของบริษัทก่อน",
  screener_ticker_any: "ทั้งหมด",
  screener_run: "รันการคัดกรอง",
  screener_run_multi: "รันการคัดกรอง ({count} เงื่อนไข)",
  screener_running: "กำลังรัน...",
  screener_disclaimer:
    "แต่ละคอลัมน์ด้านล่างแสดงว่าบริษัทนั้นเป็นไปตามเงื่อนไขนั้นในปัจจุบันหรือไม่ นี่เป็นเพียงตัวกรองเทียบกันตามเกณฑ์ของคุณเอง ไม่ใช่คำแนะนำให้ซื้อหรือขายสิ่งใด",
  screener_error: "ไม่สามารถรันการคัดกรองได้",
  screener_table_company: "บริษัท",
  screener_table_na: "ไม่มีข้อมูล",

  // Portfolio page
  portfolio_title: "พอร์ต",
  portfolio_intro:
    "ทุกสถานะการถือครองที่คุณบันทึกไว้ จัดกลุ่มตามบริษัท พร้อมเหตุผลที่คุณซื้อซึ่งถูกบันทึกไว้ ณ เวลาที่ซื้อ เทียบกับสถานะปัจจุบันของเหตุผลนั้น",
  portfolio_ask_agent: "ถามเอเจนต์",
  portfolio_loading: "กำลังโหลดพอร์ต...",
  portfolio_error: "ไม่สามารถโหลดพอร์ตของคุณได้",
  portfolio_empty: "ยังไม่มีสถานะการถือครอง บันทึกการซื้อจากแดชบอร์ดเพื่อให้แสดงที่นี่",
  portfolio_position_summary: "{quantity} หน่วย ราคา ${price} เมื่อวันที่ {date}",
  portfolio_bought_for: "ซื้อเพราะ: {description} (ตอนซื้อคือ {status})",
  portfolio_no_reason: "ไม่มีเหตุผลแนบมากับการซื้อครั้งนี้",
  portfolio_value_at_purchase: "ตอนซื้อ:",
  portfolio_value_now: "ตอนนี้:",
  portfolio_status_unknown: "ไม่ทราบ",
  portfolio_status_still_true: "ยังคงเป็นจริง",
  portfolio_status_broken: "ไม่เป็นจริงอีกต่อไป",
  portfolio_delete_position_aria: "ลบสถานะการถือครอง",

  // Profiles page
  profiles_title: "โปรไฟล์นักลงทุน",
  profiles_intro:
    "โปรไฟล์อธิบายระดับความเสี่ยงที่ยอมรับได้และเป้าหมายของคุณ ใช้โดยฟีเจอร์ปรับให้เหมาะกับผู้ใช้แบบมีค่าใช้จ่ายบนแดชบอร์ด — ตัวโปรไฟล์เองไม่ได้ทำอะไรโดยลำพัง",
  profiles_new_title: "โปรไฟล์ใหม่",
  profiles_new_description: "เพิ่มโปรไฟล์นักลงทุนที่นำกลับมาใช้ซ้ำได้",
  profiles_field_name: "ชื่อ",
  profiles_field_risk: "ระดับความเสี่ยงที่ยอมรับได้",
  profiles_risk_placeholder: "เช่น ปานกลาง",
  profiles_field_horizon: "ระยะเวลาการลงทุน",
  profiles_horizon_placeholder: "เช่น 5-10 ปี",
  profiles_field_size: "ขนาดสถานะ (%)",
  profiles_field_objective: "เป้าหมาย",
  profiles_objective_placeholder: "เช่น การเติบโตของเงินทุนในระยะยาว",
  profiles_submit: "เพิ่มโปรไฟล์",
  profiles_submit_pending: "กำลังบันทึก...",
  profiles_loading: "กำลังโหลดโปรไฟล์...",
  profiles_error: "ไม่สามารถโหลดโปรไฟล์ได้",
  profiles_err_name: "กรุณาตั้งชื่อโปรไฟล์",
  profiles_err_size: "ขนาดสถานะ % ต้องเป็นตัวเลข",
  profiles_err_default: "ไม่สามารถสร้างโปรไฟล์นี้ได้",
  profiles_delete_aria: "ลบโปรไฟล์",
  profiles_card_risk: "ความเสี่ยง: {value}",
  profiles_card_horizon: "ระยะเวลา: {value}",
  profiles_card_size: "ขนาดสถานะ: {value}%",
  profiles_card_objective: "เป้าหมาย: {value}",

  // Status badge
  status_supported: "ได้รับการยืนยัน",
  status_weakened: "อ่อนแรงลง",
  status_broken: "ไม่เป็นจริงแล้ว",
  status_not_enough_data: "ข้อมูลไม่เพียงพอ",
}

export const translations = { en, th }

export type TranslationKey = keyof typeof en

// The 3 built-in reasons' descriptions come from the backend as plain
// English strings (tools.REASON_DEFS) -- they're data, not UI chrome, so
// they don't flow through the `t()` dictionary above. This is a small,
// separate lookup (keyed by reason_key, the one stable identifier) so
// they can still show in Thai. Deliberately NOT applied to custom
// reasons -- those are free text the user wrote themselves, and
// auto-translating someone's own words would be misleading, not helpful.
export const builtinReasonDescriptions: Record<string, { en: string; th: string }> = {
  revenue_growth: {
    en: "Revenue growth must exceed 10% YoY",
    th: "รายได้ต้องเติบโตมากกว่า 10% เทียบปีก่อนหน้า (YoY)",
  },
  operating_margin: {
    en: "Operating margin must stay at or above 20%",
    th: "อัตรากำไรจากการดำเนินงานต้องอยู่ที่ 20% ขึ้นไป",
  },
  debt_growth: {
    en: "Long-term debt must not grow more than 15% YoY",
    th: "หนี้สินระยะยาวต้องเติบโตไม่เกิน 15% เทียบปีก่อนหน้า (YoY)",
  },
}
