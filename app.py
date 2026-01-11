import streamlit as st
import pandas as pd
import plotly.express as px

from db import init_db, upsert_default_admin, get_conn, replace_week_data
from auth import login, create_user, ensure_hashed_passwords

st.set_page_config(page_title="PMO Dashboard", layout="wide")

def load_data():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM fact", conn)
    conn.close()
    return df

def filters(df):
    st.sidebar.header("الفلاتر")

    week = st.sidebar.selectbox("الأسبوع", ["(الكل)"] + sorted(df["week_date"].dropna().unique().tolist()))
    m = st.sidebar.multiselect("البلدية", sorted(df["municipality"].dropna().unique().tolist()))
    e = st.sidebar.multiselect("الجهة", sorted(df["entity"].dropna().unique().tolist()))
    p = st.sidebar.multiselect("المشروع", sorted(df["project"].dropna().unique().tolist()))

    out = df.copy()
    if week != "(الكل)":
        out = out[out["week_date"] == week]
    if m:
        out = out[out["municipality"].isin(m)]
    if e:
        out = out[out["entity"].isin(e)]
    if p:
        out = out[out["project"].isin(p)]
    return out

def dashboard():
    st.title("PMO Dashboard")
    df = load_data()
    if df.empty:
        st.info("لا توجد بيانات حتى الآن. روحي Update Data وارفعي الإكسل.")
        return

    fdf = filters(df)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("عدد المشاريع", int(fdf["project"].nunique()))
    c2.metric("عدد الجهات", int(fdf["entity"].nunique()))
    c3.metric("إجمالي الميزانية", f"{fdf['budget'].fillna(0).sum():,.0f}")
    c4.metric("متوسط الإنجاز", f"{fdf['progress'].fillna(0).mean():.1f}%")

    st.divider()

    left, right = st.columns(2)
    with left:
        st.subheader("حسب الحالة")
        s = fdf["status"].fillna("غير محدد").value_counts().reset_index()
        s.columns = ["status", "count"]
        st.plotly_chart(px.bar(s, x="status", y="count"), use_container_width=True)

    with right:
        st.subheader("الميزانية حسب البلدية")
        b = fdf.groupby("municipality", dropna=False)["budget"].sum().reset_index()
        b["municipality"] = b["municipality"].fillna("غير محدد")
        st.plotly_chart(px.bar(b, x="municipality", y="budget"), use_container_width=True)

    st.subheader("تفاصيل")
    st.dataframe(fdf.drop(columns=["id"], errors="ignore"), use_container_width=True, hide_index=True)

def update_data(user):
    st.title("Update Data")
    if user["role"] not in ["admin", "editor"]:
        st.error("ليس لديك صلاحية.")
        return

    file = st.file_uploader("ارفع Excel (Sheet اسمها Data)", type=["xlsx"])
    week_date = st.text_input("week_date (مثال: 2026-01-11)")

    if file and week_date:
        df = pd.read_excel(file, sheet_name="Data")

        expected = ["municipality", "entity", "project", "status", "budget", "progress"]
        missing = [c for c in expected if c not in df.columns]
        if missing:
            st.error(f"أعمدة ناقصة: {missing}")
            return

        df = df[expected].copy()
        df["week_date"] = week_date
        df["budget"] = pd.to_numeric(df["budget"], errors="coerce")
        df["progress"] = pd.to_numeric(df["progress"], errors="coerce")

        replace_week_data(df, week_date)
        st.success("تم التحديث ✅")

def users_admin(user):
    st.title("Users (Admin)")
    if user["role"] != "admin":
        st.error("Admin فقط.")
        return

    with st.form("create_user"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        role = st.selectbox("Role", ["viewer", "editor", "admin"])
        ok = st.form_submit_button("Create")
    if ok:
        create_user(username, password, role)
        st.success("تم إنشاء المستخدم ✅")

def login_screen():
    st.title("Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        user = login(u, p)
        if user:
            st.session_state["user"] = user
            st.rerun()
        else:
            st.error("بيانات غير صحيحة")

def main():
    init_db()
    upsert_default_admin()
    ensure_hashed_passwords()

    user = st.session_state.get("user")
    if not user:
        login_screen()
        return

    st.sidebar.success(f"مرحبًا {user['username']} ({user['role']})")
    page = st.sidebar.radio("Menu", ["Dashboard", "Update Data", "Users (Admin)", "Logout"])

    if page == "Dashboard":
        dashboard()
    elif page == "Update Data":
        update_data(user)
    elif page == "Users (Admin)":
        users_admin(user)
    else:
        st.session_state.pop("user", None)
        st.rerun()

if __name__ == "__main__":
    main()
