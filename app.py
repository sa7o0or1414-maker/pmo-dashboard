import pandas as pd
import streamlit as st
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
def color_status_cell(val):
    val = str(val).strip()
    if val == "متأخر":
        return "background-color: #fde2e2; font-weight: bold"
    elif val == "منتظم":
        return "background-color: #e6f4ea; font-weight: bold"
    elif val == "متعثر":
        return "background-color: #fff4e5; font-weight: bold"
    elif val == "متوقف":
        return "background-color: #eeeeee; font-weight: bold"
    else:
        return ""

styled_df = (
    fdf
    .drop(columns=["id"], errors="ignore")
    .style
    .applymap(color_status_cell, subset=["status"])
)

st.subheader("تفاصيل المشاريع")
st.dataframe(
    styled_df,
    use_container_width=True,
    hide_index=True
)


def update_data(user):
    st.title("Update Data")

    if user["role"] not in ["admin", "editor"]:
        st.error("ليس لديك صلاحية.")
        return

    # 1) رفع الملف
    file = st.file_uploader("ارفع ملف Excel", type=["xlsx"])

    # 2) إدخال تاريخ الأسبوع
    week_date = st.text_input("week_date (مثال: 2026-01-11)")

    if not file:
        st.info("ارفعي ملف الإكسل أولًا.")
        return

    # 3) اختيار الشيت
    xls = pd.ExcelFile(file)
    sheet = st.selectbox("اختاري الشيت اللي فيه البيانات", xls.sheet_names)
    df_raw = pd.read_excel(xls, sheet_name=sheet)

    if df_raw.empty:
        st.error("الشيت المختار فاضي.")
        return

    # 4) تعيين الأعمدة
    st.caption("اختاري من القوائم: أي عمود يمثل كل حقل")
    cols = ["(لا يوجد)"] + df_raw.columns.tolist()

    c1, c2, c3 = st.columns(3)
    with c1:
        col_municipality = st.selectbox("عمود البلدية", cols)
        col_entity = st.selectbox("عمود الجهة", cols)
    with c2:
        col_project = st.selectbox("عمود المشروع", cols)
        col_status = st.selectbox("عمود الحالة", cols)
    with c3:
        col_budget = st.selectbox("عمود الميزانية", cols)
        col_progress = st.selectbox("عمود نسبة الإنجاز", cols)

    if not week_date:
        st.warning("رجاءً اكتبي week_date قبل الحفظ.")
        return

    # 5) التحقق من التعيين
    selected = {
        "municipality": col_municipality,
        "entity": col_entity,
        "project": col_project,
        "status": col_status,
        "budget": col_budget,
        "progress": col_progress,
    }

    missing = [k for k, v in selected.items() if v == "(لا يوجد)"]
    if missing:
        st.error(f"اختاري الأعمدة الناقصة: {missing}")
        return

    # 6) بناء الداتا النهائية
    df = pd.DataFrame({
        "municipality": df_raw[selected["municipality"]],
        "entity": df_raw[selected["entity"]],
        "project": df_raw[selected["project"]],
        "status": df_raw[selected["status"]],
        "budget": df_raw[selected["budget"]],
        "progress": df_raw[selected["progress"]],
    })

    # 7) إضافة week_date + تنظيف
    df["week_date"] = week_date
    df["budget"] = pd.to_numeric(df["budget"], errors="coerce")
    df["progress"] = pd.to_numeric(df["progress"], errors="coerce")

    # 8) معاينة
    st.subheader("معاينة البيانات قبل الحفظ")
    st.dataframe(df.head(30), use_container_width=True, hide_index=True)

    # 9) حفظ
    if st.button("حفظ وتحديث بيانات هذا الأسبوع"):
        replace_week_data(df, week_date)
        st.success("تم تحديث البيانات بنجاح ✅")


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
