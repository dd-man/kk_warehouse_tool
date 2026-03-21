import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection

# --- 1. 建立连接 ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. 数据读取函数 (替代 get_data) ---
def get_inventory():
    # 读取 Inventory 工作表，ttl=0 确保每次刷新页面都获取最新数据
    return conn.read(worksheet="Inventory", ttl="0s").dropna(how="all")

def get_categories():
    # 读取 Categories 工作表
    return conn.read(worksheet="Categories", ttl="0s").dropna(how="all")

# --- 3. 页面布局 ---
st.set_page_config(page_title="寇博实验室助手专业版", layout="wide")
st.title("📦 Lab Inventory Tracking System")

# 顶部并列标签页
tab_dashboard, tab_action, tab_add, tab_settings = st.tabs([
    "📊 库存看板",
    "🔄 领用入库",
    "➕ 新增用品",
    "⚙️ 系统设置"
])

# --- Tab 1: 库存看板 ---
with tab_dashboard:
    df = get_inventory()
    if df.empty:
        st.info("💡 仓库目前没有物资，请先录入。")
    else:
        # 注意：这里使用的列名必须与你 Google 表格第一行的表头完全一致
        # 预警逻辑
        low_stock_df = df[df["当前库存"] <= df["安全库存"]]

        c1, c2 = st.columns(2)
        c1.metric("物资种类", len(df))
        c2.metric("预警物品数量", len(low_stock_df), delta=-len(low_stock_df), delta_color="inverse")

        if not low_stock_df.empty:
            st.error(f"⚠️ 需补货清单: {', '.join(low_stock_df['物品名称'].tolist())}")

        # 库存柱状图
        muted_colors = ["#8EADC1", "#A8BBA1", "#D4C4A8", "#B8A1B8", "#D9B496", "#97A7B3"]
        fig = px.bar(
            df,
            x="物品名称",
            y="当前库存",
            color="分类",
            title="实时库存分布",
            color_discrete_sequence=muted_colors,
        )
        st.plotly_chart(fig, use_container_width=True)

        # 样式：物品名称加红
        def highlight_low_stock(row):
            is_low = row["当前库存"] <= row["安全库存"]
            color = "color: #EF5350; font-weight: bold;" if is_low else ""
            return [color if col == "物品名称" else "" for col in row.index]

        styled_df = df.style.apply(highlight_low_stock, axis=1).format({
    "当前库存": "{:.2f}",
    "安全库存": "{:.2f}"
})
        st.subheader("库存明细表")
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

# --- Tab 2: 领用入库 ---
with tab_action:
    # 显示 session_state 的消息提示
if "msg" in st.session_state:
    st.success(st.session_state["msg"])  # 若是错误可以用 st.error
    del st.session_state["msg"]
    df = get_inventory()
    if not df.empty:
        st.subheader("快速库存变动")
        item_name = st.selectbox("1️⃣ 选择物品", df["物品名称"].tolist())
        num = st.number_input("2️⃣ 数量", min_value=1, value=1)
        st.write("3️⃣ 确认操作")
        col_in, col_out = st.columns(2)

       # 入库
if col_in.button("📥 确认入库", use_container_width=True):
    df.loc[df["物品名称"] == item_name, "当前库存"] += num
    conn.update(worksheet="Inventory", data=df)
    st.session_state["msg"] = f"✅ {item_name} 已增加 {num}"
    st.rerun()

# 领用
if col_out.button("📤 确认领用", use_container_width=True):
    current = df.loc[df["物品名称"] == item_name, "当前库存"].values[0]
    if current >= num:
        df.loc[df["物品名称"] == item_name, "当前库存"] -= num
        conn.update(worksheet="Inventory", data=df)
        st.session_state["msg"] = f"✅ {item_name} 已领用 {num}"
        st.rerun()
    else:
        st.session_state["msg"] = f"❌ 库存不足！当前仅剩 {current}"
        st.rerun()
    else:
        st.info("请先录入物资")

# --- Tab 3: 新增用品 ---
with tab_add:
    st.subheader("录入新物资档案")
    # 获取现有分类和物品
    cat_df = get_categories()
    cat_list = cat_df["分类名称"].tolist() if not cat_df.empty else []
    df_inv = get_inventory()
    existing_items = df_inv["物品名称"].tolist() if not df_inv.empty else []

    with st.form("add_item_form", clear_on_submit=True):
        c_name, c_cat = st.columns(2)
        name = c_name.text_input("物品名称 *")
        category = c_cat.selectbox("所属分类", cat_list if cat_list else ["请先添加分类"])

        c_brand, c_no = st.columns(2)
        brand = c_brand.text_input("品牌/生产厂家")
        item_no = c_no.text_input("货号")

        c_spec, c_loc = st.columns(2)
        spec = c_spec.text_input("规格型号")
        location = c_loc.text_input("存放位置 (如: A-102)")

        c_curr, c_safe, c_unit = st.columns(3)
        curr = c_curr.number_input("初始库存", min_value=0, value=0)
        safe = c_safe.number_input("预警数值", min_value=0, value=5)
        unit = c_unit.text_input("单位", value="个")

        if st.form_submit_button("确认提交档案"):
            if not name:
                st.warning("⚠️ 请输入物品名称")
            elif name in existing_items:
                st.error(f"❌ 物品 “{name}” 已存在")
            else:
                # 构造新行并合并
                new_row = pd.DataFrame([[name, category, brand, item_no, spec, location, curr, safe, unit]], 
                                       columns=df_inv.columns)
                df_updated = pd.concat([df_inv, new_row], ignore_index=True)
                conn.update(worksheet="Inventory", data=df_updated)
                st.success(f"✅ 成功录入 {name}！")
                st.rerun()

# --- Tab 4: 系统设置 ---
with tab_settings:
    st.subheader("分类管理")
    # 添加分类
    new_cat = st.text_input("输入新分类名称")
    cat_df = get_categories()
    if st.button("➕ 添加分类"):
        existing_cats = cat_df["分类名称"].tolist() if not cat_df.empty else []
        if new_cat and new_cat not in existing_cats:
            new_row = pd.DataFrame([[new_cat]], columns=["分类名称"])
            cat_updated = pd.concat([cat_df, new_row], ignore_index=True)
            conn.update(worksheet="Categories", data=cat_updated)
            st.success(f"✅ 分类 “{new_cat}” 添加成功")
            st.rerun()
        else:
            st.error("分类已存在或名称为空")

    # 删除分类
    if not cat_df.empty:
        cat_to_del = st.selectbox("选择要删除的分类", cat_df["分类名称"].tolist(), key="del_cat_select")
        confirm_del = st.checkbox(f"确认删除分类 “{cat_to_del}”", key="del_cat_confirm")
        if st.button("🗑️ 删除分类"):
            if confirm_del:
                cat_updated = cat_df[cat_df["分类名称"] != cat_to_del]
                conn.update(worksheet="Categories", data=cat_updated)
                st.warning(f"⚠️ 分类 “{cat_to_del}” 已被删除")
                st.rerun()
    
    st.divider()
    st.subheader("物资维护")
    df_inv = get_inventory()
    if not df_inv.empty:
        item_to_del = st.selectbox("选择要彻底删除的物资", df_inv["物品名称"].tolist(), key="del_item_select")
        if st.button("⚠️ 彻底删除物资"):
            df_updated = df_inv[df_inv["物品名称"] != item_to_del]
            conn.update(worksheet="Inventory", data=df_updated)
            st.error(f"🔥 {item_to_del} 已永久移除")
            st.rerun()

