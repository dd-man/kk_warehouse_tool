import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px

# --- 1. 数据库初始化 ---
def init_db():
    conn = sqlite3.connect('warehouse_v6.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS inventory
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE,
                  category TEXT,
                  current_stock INTEGER,
                  safe_stock INTEGER,
                  unit TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS categories
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE)''')
    
    c.execute("SELECT COUNT(*) FROM categories")
    if c.fetchone()[0] == 0:
        default_cats = [("办公用品",), ("清洁用品",), ("茶水间",)]
        c.executemany("INSERT INTO categories (name) VALUES (?)", default_cats)
    
    conn.commit()
    return conn

conn = init_db()

# --- 2. 数据库操作通用函数 ---
def get_data(table):
    return pd.read_sql_query(f"SELECT * FROM {table}", conn)

def run_query(query, params=()):
    with conn:
        conn.execute(query, params)

# --- 3. 界面设计 ---
st.set_page_config(page_title="仓库助手专业版", layout="wide")

# 自定义 CSS：让表格中的红色更醒目
st.markdown("""
    <style>
    .low-stock-text { color: #d9534f; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("📦 仓库用品管理系统")

# 顶部并列菜单
tab_dashboard, tab_action, tab_add, tab_settings = st.tabs([
    "📊 库存看板", 
    "🔄 领用入库", 
    "➕ 新增用品", 
    "⚙️ 系统设置"
])

# --- Tab 1: 库存看板 (增加标红逻辑 & 调色) ---
with tab_dashboard:
    df = get_data("inventory")
    if df.empty:
        st.info("💡 仓库目前没有物资，请先录入。")
    else:
        # 预警逻辑处理
        low_stock_df = df[df['current_stock'] <= df['safe_stock']]
        
        c1, c2 = st.columns(2)
        c1.metric("物资种类", len(df))
        c2.metric("预警物品数量", len(low_stock_df), delta=-len(low_stock_df), delta_color="inverse")
        
        # 改进 1: 如果有预警物品，直接在指标下方列出名字
        if not low_stock_df.empty:
            st.error(f"⚠️ 需补货清单: {', '.join(low_stock_df['name'].tolist())}")

        # 改进 2: 低饱和度配色方案 (排除红色)
        # 莫兰迪色系：蓝灰、豆蔻绿、淡黄、藕荷、浅橘、青灰
        muted_colors = ['#8EADC1', '#A8BBA1', '#D4C4A8', '#B8A1B8', '#D9B496', '#97A7B3']
        
        fig = px.bar(df, x="name", y="current_stock", color="category", 
                     title="实时库存分布", 
                     labels={'current_stock':'数量', 'name':'物品名称', 'category':'分类'},
                     color_discrete_sequence=muted_colors) # 应用自定义色系
        
        fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)
        
        # 改进 3: 明细表标红逻辑
        st.subheader("库存明细表")
        
        def highlight_low_stock(row):
            # 如果当前库存 <= 安全库存，则将 'name' 列设为红色
            color = 'color: #EF5350; font-weight: bold;' if row.current_stock <= row.safe_stock else ''
            return [color if col == 'name' else '' for col in row.index]

        # 使用 Pandas Styler 进行渲染
        styled_df = df.style.apply(highlight_low_stock, axis=1)
        
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

# --- Tab 2: 领用入库 ---
with tab_action:
    df = get_data("inventory")
    if not df.empty:
        st.subheader("快速库存变动")
        item_name = st.selectbox("1. 选择物品", df['name'].tolist(), key="action_select")
        num = st.number_input("2. 数量", min_value=1, value=1)
        st.write("确认操作")
        col_btn1, col_btn2 = st.columns(2)
        
        if col_btn1.button("📥 确认入库", use_container_width=True):
            run_query("UPDATE inventory SET current_stock = current_stock + ? WHERE name = ?", (num, item_name))
            st.success(f"✅ {item_name} 已增加 {num}")
            st.rerun()
            
        if col_btn2.button("📤 确认领用", use_container_width=True):
            current = df[df['name'] == item_name]['current_stock'].values[0]
            if current >= num:
                run_query("UPDATE inventory SET current_stock = current_stock - ? WHERE name = ?", (num, item_name))
                st.success(f"✅ {item_name} 已领用 {num}")
                st.rerun()
            else:
                st.error(f"❌ 库存不足！当前仅剩 {current}")
    else:
        st.info("请先录入物资")

# --- Tab 3: 新增用品 ---
with tab_add:
    st.subheader("录入新物资")
    cat_list = get_data("categories")['name'].tolist()
    existing_items = get_data("inventory")['name'].tolist()
    
    with st.form("add_item_form", clear_on_submit=True):
        name = st.text_input("物品名称")
        category = st.selectbox("所属分类", cat_list if cat_list else ["请先添加分类"])
        c1, c2, c3 = st.columns(3)
        curr = c1.number_input("初始库存", min_value=0, value=0)
        safe = c2.number_input("预警数值", min_value=0, value=5)
        unit = c3.text_input("单位", value="个")
        
        submit_button = st.form_submit_button("确认提交")
        
        if submit_button:
            if not name:
                st.warning("⚠️ 请输入物品名称")
            elif not cat_list:
                st.error("❌ 尚未创建任何分类")
            elif name in existing_items:
                st.error(f"❌ 物品 '{name}' 已存在")
            else:
                run_query("INSERT INTO inventory (name, category, current_stock, safe_stock, unit) VALUES (?,?,?,?,?)",
                          (name, category, curr, safe, unit))
                st.success(f"✅ 成功录入 {name}！")
                st.rerun()

# --- Tab 4: 系统设置 ---
with tab_settings:
    st.subheader("分类管理")
    new_cat = st.text_input("输入新分类名称", key="new_cat_input")
    if st.button("➕ 添加分类"):
        existing_cats = get_data("categories")['name'].tolist()
        if not new_cat:
            st.warning("请输入分类名称")
        elif new_cat in existing_cats:
            st.error(f"❌ 分类 '{new_cat}' 已存在")
        else:
            run_query("INSERT INTO categories (name) VALUES (?)", (new_cat,))
            st.success(f"✅ 分类 '{new_cat}' 添加成功")
            st.rerun()
    
    st.divider()
    cat_df = get_data("categories")
    if not cat_df.empty:
        cat_to_del = st.selectbox("选择要删除的分类", cat_df['name'].tolist())
        if st.button("🗑️ 删除选中分类"):
            items_in_cat = get_data("inventory")
            if cat_to_del in items_in_cat['category'].tolist():
                st.error(f"❌ 无法删除：'{cat_to_del}' 下尚有物资。")
            else:
                run_query("DELETE FROM categories WHERE name = ?", (cat_to_del,))
                st.warning(f"🗑️ 分类 '{cat_to_del}' 已删除")
                st.rerun()
    
    st.divider()
    st.subheader("物资维护")
    inv_df = get_data("inventory")
    if not inv_df.empty:
        item_to_del = st.selectbox("选择要彻底删除的物资", inv_df['name'].tolist())
        if st.button("⚠️ 彻底删除物资"):
            run_query("DELETE FROM inventory WHERE name = ?", (item_to_del,))
            st.error(f"🔥 {item_to_del} 已永久移除")
            st.rerun()