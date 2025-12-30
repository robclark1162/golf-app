# Good as off 22-0902025
import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client, Client
import os
import base64
import altair as alt

if "user" not in st.session_state:
    st.session_state["user"] = None
if "access_token" not in st.session_state:
    st.session_state["access_token"] = None
if "refresh_token" not in st.session_state:
    st.session_state["refresh_token"] = None

def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

# Load once at top
redcap_base64 = get_base64_image("red_cap.png")
hat_icon = f'<img src="data:image/png;base64,{redcap_base64}" width="20"/>'


# --- Supabase Connection ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://aqaiziylxougtlaihlor.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFxYWl6aXlseG91Z3RsYWlobG9yIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTgxNjk1NTMsImV4cCI6MjA3Mzc0NTU1M30.kqhyv4WIFw0SQUoNocX_8TNXouVm4XUzIGO2FY0nhVY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# Try to restore session if logged in previously
if st.session_state["refresh_token"] and not st.session_state["user"]:
    try:
        session = supabase.auth.refresh_session(refresh_token=st.session_state["refresh_token"])
        if session and session.user:
            st.session_state["user"] = session.user.email
            st.session_state["access_token"] = session.session.access_token
            st.session_state["refresh_token"] = session.session.refresh_token
    except Exception:
        pass  # token may have expired, user must log in again

# --- DB Helpers (Supabase) ---
def load_players():
    response = supabase.table("players").select("player_id, name, full_name, image_url").order("name").execute()
    return pd.DataFrame(response.data)


def insert_player(name: str):
    supabase.table("players").insert({"name": name, "Full Name": full_name, "Image":image_url}).execute()


def delete_player(player_id: int):
    supabase.table("players").delete().eq("player_id", player_id).execute()

def update_player(name, full_name="", image_url=""):    
    supabase.table("players").update({
        "name": name,
        "full_name": full_name,
        "image_url": image_url
        }).eq("player_id").eq("player_id").execute()

def load_courses():
    response = supabase.table("courses").select("course_id, name").order("name").execute()
    return pd.DataFrame(response.data)


def insert_course(name: str):
    supabase.table("courses").insert({"name": name}).execute()


def delete_course(course_id: int):
    supabase.table("courses").delete().eq("course_id", course_id).execute()


def load_scores():
    response = supabase.table("scores").select(
        """
        score,
        birdies,
        eagles,
        hat,
        players ( player_id, name ),
        rounds ( round_id, round_date, courses ( course_id, name ) )
        """
    ).execute()

    df = pd.DataFrame(response.data)

    if df.empty:
        return df

    # Flatten nested JSON
    df["player_id"] = df["players"].apply(lambda x: x["player_id"] if x else None)
    df["player"] = df["players"].apply(lambda x: x["name"] if x else None)
    df["round_id"] = df["rounds"].apply(lambda x: x["round_id"] if x else None)
    df["round_date"] = df["rounds"].apply(lambda x: x["round_date"] if x else None)
    df["course_id"] = df["rounds"].apply(lambda x: x["courses"]["course_id"] if x and x["courses"] else None)
    df["course"] = df["rounds"].apply(lambda x: x["courses"]["name"] if x and x["courses"] else None)

    # Drop nested objects
    df = df.drop(columns=["players", "rounds"])

    return df[
        ["round_id", "round_date", "course", "player_id", "player", "score", "birdies", "eagles", "hat"]
    ]


def insert_round(round_date, course_id, scores):
    # Insert round
    round_resp = supabase.table("rounds").insert(
        {"round_date": str(round_date), "course_id": course_id}
    ).execute()

    if not round_resp.data:
        return
    round_id = round_resp.data[0]["round_id"]

    # Insert scores
    score_rows = []
    for player_id, (score, birdies, eagles, hat) in scores.items():
        if score is not None:
            score_rows.append({
                "round_id": round_id,
                "player_id": player_id,
                "score": score,
                "birdies": birdies,
                "eagles": eagles,
                "hat": hat,
            })
    if score_rows:
        supabase.table("scores").insert(score_rows).execute()


def update_score(round_id, player_id, score, birdies, eagles, hat):
    supabase.table("scores").update({
        "score": score,
        "birdies": birdies,
        "eagles": eagles,
        "hat": hat
    }).eq("round_id", round_id).eq("player_id", player_id).execute()



# --- Authentication state ---
if "user" not in st.session_state:
    st.session_state["user"] = None


st.title("🏌️ Golf Twitchers Competition Tracker")

if st.session_state["user"] is None:
    st.subheader("🔑 Login")
    st.logo("twitchers.jpg", size="large")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if res.user is not None:
                # ✅ Store tokens & email
                st.session_state["user"] = res.user.email
                st.session_state["access_token"] = res.session.access_token
                st.session_state["refresh_token"] = res.session.refresh_token

                st.success(f"✅ Welcome {st.session_state['user']}")
                st.rerun()
            else:
                st.error("❌ Invalid credentials")
        except Exception as e:
            st.error(f"❌ Login failed: {str(e)}")

    st.stop()  # ⛔ stop app until logged in

else:
    # --- Sidebar user info + logout ---
    st.sidebar.success(f"Logged in as {st.session_state['user']}")
    if st.sidebar.button("Logout"):
        st.session_state["user"] = None
        st.session_state["access_token"] = None
        st.session_state["refresh_token"] = None
        st.rerun()

    # --- App Menu (only after login) ---
    menu = st.sidebar.radio(
        "Menu",
        ["View Scores", "Summary", "Scores by Day", "Add Round", "Edit Round", "Manage Players", "Manage Courses"]
    )

# --- View Scores ---
    if menu == "View Scores":
        st.subheader("All Scores")
        df = load_scores()

        display_df = df.drop(
            columns=["player_id", "course_id", "round_id", "score_id"],
            errors="ignore"
        )
        with st.expander("📋 Scrores"):
            st.dataframe(display_df.reset_index(drop=True), use_container_width=True)

        # --- Average Scores ---
        st.subheader("Average Scores by Player")
        avg_df = df.groupby("player")["score"].mean().reset_index()
        st.bar_chart(avg_df.set_index("player"))

        # --- Score trends (all players) ---
        st.subheader("📊 Score Trends Over Time")
        if not df.empty:
            chart = (
                alt.Chart(df)
                .mark_line(point=True)
                .encode(
                    x="round_date:T",
                    y="score:Q",
                    color="player:N",
                    tooltip=["round_date:T", "player:N", "score:Q", "course:N"]
                )
                .properties(height=400)
            )
            st.altair_chart(chart, use_container_width=True)

            # --- Single player dropdown ---
            players = sorted(df["player"].unique())
            player_sel = st.selectbox("🔍 View single player's scores:", players, key="view_scores_player")
            ps = df[df["player"] == player_sel]
            if not ps.empty:
                player_chart = (
                    alt.Chart(ps)
                    .mark_line(point=True)
                    .encode(
                        x="round_date:T",
                        y="score:Q",
                        tooltip=["round_date:T", "score:Q", "course:N"]
                    )
                    .properties(title=f"{player_sel} Scores Over Time", height=300)
                )
                st.altair_chart(player_chart, use_container_width=True)
