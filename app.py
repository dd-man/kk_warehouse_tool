import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px

# --------------------------------------------------------------
# 1️⃣ 数据库初始化（版本升级至 v7）
# --------------------------------------------------------------
def init_db():
    """
    初始化/升级数据库结构（v7）
    - inventory：新增 brand、item_no、spec、location 四个字段
    - categories：仅保留唯一的分类名称
    """
    conn = sqlite3.connect('warehouse_v7.db', check_same_thread=False)
    c = conn.cursor()

    # 物品表（inventory）
    c.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            category TEXT,
            brand TEXT,
            item_no TEXT,
            spec TEXT,
            location TEXT,
            current_stock INTEGER,
            safe_stock INTEGER,
            unit TEXT
        )
    ''')

    # 分类表（categories）
    c.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    ''')

    # 若分类表为空，写入默认分类
    c.execute("SELECT COUNT(*) FROM categories")
    if c.fetchone()[0] == 0:
        default_cats = [("办公用品",), ("实验用品",), ("日常耗材",)]
        c.executemany("INSERT INTO categories (name) VALUES (?)", default_cats)

    conn.commit()
    return conn

conn = init_db()

# --------------------------------------------------------------
# 2️⃣ 数据库操作函数
# --------------------------------------------------------------
def get_data(table: str) -> pd.DataFrame:
    """读取指定表的全部数据并返回 DataFrame"""
    return pd.read_sql_query(f"SELECT * FROM {table}", conn)

def run_query(query: str, params=()):
    """执行写入类 SQL 语句（INSERT / UPDATE / DELETE）"""
    with conn:
        conn.execute(query, params)

# --------------------------------------------------------------
# 3️⃣ 页面布局
# --------------------------------------------------------------
st.set_page_config(page_title="仓库助手专业版", layout="wide")
st.title("📦 Lab Inventory Tracking System")

# 顶部并列标签页
tab_dashboard, tab_action, tab_add, tab_settings = st.tabs([
    "📊 库存看板",
    "🔄 领用入库",
    "➕ 新增用品",
    "⚙️ 系统设置"
])

# -----------------------------------------------------------------
# Tab 1️⃣：库存看板
# -----------------------------------------------------------------
with tab_dashboard:
    df = get_data("inventory")
    if df.empty:
        st.info("💡 仓库目前没有物资，请先录入。")
    else:
        # 1️⃣ 预警逻辑
        low_stock_df = df[df["current_stock"] <= df["safe_stock"]]

        c1, c2 = st.columns(2)
        c1.metric("物资种类", len(df))
        c2.metric(
            "预警物品数量",
            len(low_stock_df),
            delta=-len(low_stock_df),
            delta_color="inverse",
        )

        if not low_stock_df.empty:
            st.error(f"⚠️ 需补货清单: {', '.join(low_stock_df['name'].tolist())}")

        # 2️⃣ 库存柱状图
        muted_colors = [
            "#8EADC1",
            "#A8BBA1",
            "#D4C4A8",
            "#B8A1B8",
            "#D9B496",
            "#97A7B3",
        ]
        fig = px.bar(
            df,
            x="name",
            y="current_stock",
            color="category",
            title="实时库存分布",
            labels={"current_stock": "数量", "name": "物品名称", "category": "分类"},
            color_discrete_sequence=muted_colors,
        )
        st.plotly_chart(fig, use_container_width=True)

        # 3️⃣ 表格展示（中文列名）
        display_df = df[
            [
                "name",
                "category",
                "brand",
                "item_no",
                "spec",
                "location",
                "current_stock",
                "safe_stock",
                "unit",
            ]
        ]
        display_df.columns = [
            "物品名称",
            "分类",
            "品牌/厂家",
            "货号",
            "规格",
            "存放位置",
            "当前库存",
            "安全库存",
            "单位",
        ]

        # 4️⃣ 样式：低库存行高亮、物品名称加红
        def highlight_low_stock(row):
            is_low = row["当前库存"] <= row["安全库存"]
            color = "color: #EF5350; font-weight: bold;" if is_low else ""
            return [color if col == "物品名称" else "" for col in row.index]

        styled_df = display_df.style.apply(highlight_low_stock, axis=1)
        st.subheader("库存明细表")
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

# -----------------------------------------------------------------
# Tab 2️⃣：领用入库
# -----------------------------------------------------------------
with tab_action:
    df = get_data("inventory")
    if not df.empty:
        st.subheader("快速库存变动")
        item_name = st.selectbox("1️⃣ 选择物品", df["name"].tolist())
        num = st.number_input("2️⃣ 数量", min_value=1, value=1)
        st.write("3️⃣ 确认操作")
        col_in, col_out = st.columns(2)

        if col_in.button("📥 确认入库", use_container_width=True):
            run_query(
                "UPDATE inventory SET current_stock = current_stock + ? WHERE name = ?",
                (num, item_name),
            )
            st.success(f"✅ {item_name} 已增加 {num}")
            st.rerun()

        if col_out.button("📤 确认领用", use_container_width=True):
            current = df[df["name"] == item_name]["current_stock"].values[0]
            if current >= num:
                run_query(
                    "UPDATE inventory SET current_stock = current_stock - ? WHERE name = ?",
                    (num, item_name),
                )
                st.success(f"✅ {item_name} 已领用 {num}")
                st.rerun()
            else:
                st.error(f"❌ 库存不足！当前仅剩 {current}")
    else:
        st.info("请先录入物资")

# -----------------------------------------------------------------
# Tab 3️⃣：新增用品
# -----------------------------------------------------------------
with tab_add:
    st.subheader("录入新物资档案")
    cat_list = get_data("categories")["name"].tolist()
    existing_items = get_data("inventory")["name"].tolist()

    with st.form("add_item_form", clear_on_submit=True):
        # 第一行：基础信息
        c_name, c_cat = st.columns(2)
        name = c_name.text_input("物品名称 *")
        category = c_cat.selectbox(
            "所属分类", cat_list if cat_list else ["请先添加分类"]
        )

        # 第二行：档案信息（新增字段）
        c_brand, c_no = st.columns(2)
        brand = c_brand.text_input("品牌/生产厂家")
        item_no = c_no.text_input("货号")

        c_spec, c_loc = st.columns(2)
        spec = c_spec.text_input("规格型号")
        location = c_loc.text_input("存放位置 (如: A-102)")

        # 第三行：数量信息
        c_curr, c_safe, c_unit = st.columns(3)
        curr = c_curr.number_input("初始库存", min_value=0, value=0)
        safe = c_safe.number_input("预警数值", min_value=0, value=5)
        unit = c_unit.text_input("单位", value="个")

        submit_button = st.form_submit_button("确认提交档案")

        if submit_button:
            if not name:
                st.warning("⚠️ 请输入物品名称")
            elif name in existing_items:
                st.error(f"❌ 物品 “{name}” 已存在")
            else:
                run_query(
                    """
                    INSERT INTO inventory 
                    (name, category, brand, item_no, spec, location, current_stock, safe_stock, unit) 
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (name, category, brand, item_no, spec, location, curr, safe, unit),
                )
                st.success(f"✅ 成功录入 {name}！")
                st.rerun()

# -----------------------------------------------------------------
# Tab 4️⃣：系统设置
# -----------------------------------------------------------------
with tab_settings:
    # ---------------------- 分类管理 ----------------------
    st.subheader("分类管理")

    # ---- 添加分类 ----
    new_cat = st.text_input("输入新分类名称")
    if st.button("➕ 添加分类"):
        existing_cats = get_data("categories")["name"].tolist()
        if new_cat and new_cat not in existing_cats:
            run_query("INSERT INTO categories (name) VALUES (?)", (new_cat,))
            st.success(f"✅ 分类 “{new_cat}” 添加成功")
            st.rerun()
        else:
            st.error("分类已存在或名称为空")

    # ---- 删除分类（新功能）----
    # 1）先读取最新的分类列表
    cat_options = get_data("categories")["name"].tolist()
    if cat_options:
        cat_to_del = st.selectbox("选择要删除的分类", cat_options, key="del_cat_select")
        # 为防止误点，加入二次确认
        confirm_del = st.checkbox(
            f"确认删除分类 “{cat_to_del}”（此操作不可恢复）", key="del_cat_confirm"
        )
        if st.button("🗑️ 删除分类"):
            if confirm_del:
                # ① 删除分类
                run_query("DELETE FROM categories WHERE name = ?", (cat_to_del,))
                # ②（可选）把属于该分类的物资重新归类为 “未分类”
                # 这里保持原有物资不变，仅删除分类记录
                st.warning(f"⚠️ 分类 “{cat_to_del}” 已被删除")
                st.rerun()
            else:
                st.info("请先勾选确认框后再点击删除")
    else:
        st.info("暂无分类可删除，请先添加分类")

    st.divider()

    # ---------------------- 物资维护 ----------------------
    st.subheader("物资维护")
    inv_df = get_data("inventory")
    if not inv_df.empty:
        item_to_del = st.selectbox(
            "选择要彻底删除的物资", inv_df["name"].tolist(), key="del_item_select"
        )
        if st.button("⚠️ 彻底删除物资"):
            run_query("DELETE FROM inventory WHERE name = ?", (item_to_del,))
            st.error(f"🔥 {item_to_del} 已永久移除")
            st.rerun()
    else:
        st.info("当前暂无物资记录")
