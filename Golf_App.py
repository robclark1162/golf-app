import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client, Client
import os
import base64
import altair as alt
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

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
    response = supabase.table("players").select("player_id, name").order("name").execute()
    return pd.DataFrame(response.data)


def insert_player(name: str):
    supabase.table("players").insert({"name": name}).execute()


def delete_player(player_id: int):
    supabase.table("players").delete().eq("player_id", player_id).execute()


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
    display_df = df.drop(columns=["player_id", "course_id", "round_id", "score_id"], errors="ignore")
    st.dataframe(display_df.reset_index(drop=True), use_container_width=True)


    st.subheader("Average Scores by Player")
    avg_df = df.groupby("player")["score"].mean().reset_index()
    st.bar_chart(avg_df.set_index("player"))

elif menu == "Scores by Day":
    st.subheader("Scores by Day")

    df = load_scores()
    if df.empty:
        st.info("No scores available yet.")
    else:
        # --- Add filter date ---
        min_date = pd.to_datetime(df["round_date"]).min().date()
        start_date = st.date_input("📅 Only include scores after:", value=min_date, min_value=min_date, key="scores_by_day_date")

        # Filter data
        df = df[pd.to_datetime(df["round_date"]) >= pd.to_datetime(start_date)]

        if df.empty:
            st.warning("No scores found after selected date.")
        else:
            # Pivot scores
            scores_pivot = df.pivot_table(
                index=["round_date", "course"], 
                columns="player", 
                values="score", 
                aggfunc="first"
            ).reset_index()

            # reorder columns
            player_cols = [c for c in scores_pivot.columns if c not in ["round_date", "course"]]
            cols = ["round_date", "course"] + sorted(player_cols)
            scores_pivot = scores_pivot[cols]

            fmt_scores = {c: "{:.0f}" for c in player_cols}
            st.dataframe(scores_pivot.reset_index(drop=True), use_container_width=True)

            # Birdies/Eagles
            birds_eags = df.melt(
                id_vars=["round_date", "course", "player"], 
                value_vars=["birdies", "eagles"], 
                var_name="stat", 
                value_name="count"
            )
            birds_eags_pivot = birds_eags.pivot_table(
                index=["round_date", "course", "stat"], 
                columns="player", 
                values="count", 
                aggfunc="first"
            ).reset_index()

            birdies_table = birds_eags_pivot[birds_eags_pivot["stat"] == "birdies"].drop(columns=["stat"])
            eagles_table = birds_eags_pivot[birds_eags_pivot["stat"] == "eagles"].drop(columns=["stat"])

            # format
            pcols_bird = [c for c in birdies_table.columns if c not in ["round_date", "course"]]
            pcols_eagle = [c for c in eagles_table.columns if c not in ["round_date", "course"]]

            fmt_bird = {c: "{:.0f}" for c in pcols_bird}
            fmt_eag  = {c: "{:.0f}" for c in pcols_eagle}

            st.markdown("### Birdies")
            st.dataframe(birdies_table.reset_index(drop=True), use_container_width=True)

            st.markdown("### Eagles")
            st.dataframe(eagles_table.style.format(fmt_eag), use_container_width=True)

elif menu == "Summary":
    st.subheader("Player Summary")
    df = load_scores()

    if df.empty:
        st.info("No scores available yet.")
    else:
        # Build summary dataframe
        summary_df = (
            df.groupby("player")
            .agg(
                Rounds=("score", "count"),
                Average=("score", "mean"),
                Best=("score", "min"),
                Last=("score", "last")
            )
            .reset_index()
        )

        # Round Average
        summary_df["Average"] = summary_df["Average"].round(1)

        # Rankings
        summary_df = summary_df.sort_values("Average").reset_index(drop=True)
        summary_df.index += 1
        summary_df.insert(0, "Rank", summary_df.index)

        # Rank emojis
        summary_df["Rank"] = summary_df["Rank"].astype(str)
        if len(summary_df) > 0: summary_df.loc[0, "Rank"] = "🥇"
        if len(summary_df) > 1: summary_df.loc[1, "Rank"] = "🥈"
        if len(summary_df) > 2: summary_df.loc[2, "Rank"] = "🥉"

        # Identify latest hat-holder
        latest_round = df["round_date"].max()
        hat_holder = None
        if not pd.isnull(latest_round):
            latest_scores = df[df["round_date"] == latest_round]
            if not latest_scores.empty:
                hat_holder = latest_scores.loc[latest_scores["score"].idxmin(), "player"]

        # Player display column
        summary_df["Player Display"] = summary_df["player"].apply(
            lambda p: f"{p} 🧢" if p == hat_holder else p
        )

        # Reorder columns
        summary_df = summary_df[
            ["Rank", "Player Display", "Rounds", "Average", "Best", "Last"]
        ]

        # AgGrid interactive table
        gb = GridOptionsBuilder.from_dataframe(summary_df)
        gb.configure_selection("single")  # select one player at a time
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_default_column(resizable=True, filter=True, sortable=True)

        grid_options = gb.build()

        st.markdown("👉 Click a row to view the player's score trend")
        grid_response = AgGrid(
            summary_df,
            gridOptions=grid_options,
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            height=400,
            fit_columns_on_grid_load=True,
            allow_unsafe_jscode=True
        )

        selected = grid_response["selected_rows"]

        if selected:
            player = selected[0]["Player Display"].replace("🧢", "").strip()
            st.subheader(f"📊 {player}'s Score Trend")

            player_scores = df[df["player"] == player][["round_date", "score"]]

            if not player_scores.empty:
                chart = (
                    alt.Chart(player_scores)
                    .mark_line(point=True)
                    .encode(
                        x="round_date:T",
                        y="score:Q",
                        tooltip=["round_date:T", "score:Q"]
                    )
                    .properties(height=300)
                )
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("No scores available for this player.")
# --- Add Round ---
elif menu == "Add Round":
    st.subheader("Add a New Round")

    round_date = st.date_input("Date", value=date.today())
    courses = load_courses()
    course = st.selectbox("Course", courses["name"])
    course_id = int(courses[courses["name"] == course]["course_id"].iloc[0])

    players = load_players()
    scores = {}

    st.markdown("### Enter Scores")

    for _, row in players.iterrows():
        # Create 5 columns: Player name + 4 inputs
        col0, col1, col2, col3, col4 = st.columns([2, 2, 1, 1, 1])  

        with col0:
            st.markdown(f"**{row['name']}**")  # player name in leftmost col

        with col1:
            score = st.number_input(
                "Score",
                min_value=0, max_value=200, step=1, format="%d",
                value=None, key=f"score_new_{row['player_id']}"
            )
        with col2:
            birdies = st.number_input(
                "Birdies",
                min_value=0, max_value=18, step=1, format="%d",
                value=0, key=f"birdies_new_{row['player_id']}"
            )
        with col3:
            eagles = st.number_input(
                "Eagles",
                min_value=0, max_value=18, step=1, format="%d",
                value=0, key=f"eagles_new_{row['player_id']}"
            )
        with col4:
            hat = st.checkbox(
                "Hat",
                value=False, key=f"hat_new_{row['player_id']}"
            )

        scores[row["player_id"]] = (score, birdies, eagles, hat)

    if st.button("Save Round"):
        insert_round(round_date, course_id, scores)
        st.success("✅ Round saved!")

 
    # --- Edit Round ---
elif menu == "Edit Round":
    st.subheader("Edit Existing Rounds")

    df = load_scores()

    if df.empty:
        st.info("No rounds available.")
    else:
        # Pick round
        round_ids = df[["round_id", "round_date", "course"]].drop_duplicates()
        round_choice = st.selectbox(
            "Select Round",
            round_ids.apply(lambda x: f"{x['round_date']} - {x['course']} (ID {x['round_id']})", axis=1)
        )
        round_id = int(round_choice.split("ID ")[1].rstrip(")"))

        round_data = df[df["round_id"] == round_id]

        st.write(f"Editing round on **{round_data['round_date'].iloc[0]}** at **{round_data['course'].iloc[0]}**")

        for _, row in round_data.iterrows():
            col1, col2, col3, col4, col5 = st.columns([3,2,2,2,2])

            with col1:
                st.write(row["player"])
            with col2:
                new_score = st.number_input(
                    f"Score ({row['player']})",
                    min_value=0, max_value=200, step=1, value=int(row["score"]) if row["score"] else 0,
                    key=f"score_edit_{row['player_id']}"
                )
            with col3:
                new_birdies = st.number_input(
                    f"Birdies ({row['player']})",
                    min_value=0, max_value=18, step=1, value=int(row["birdies"]) if row["birdies"] else 0,
                    key=f"birdies_edit_{row['player_id']}"
                )
            with col4:
                new_eagles = st.number_input(
                    f"Eagles ({row['player']})",
                    min_value=0, max_value=18, step=1, value=int(row["eagles"]) if row["eagles"] else 0,
                    key=f"eagles_edit_{row['player_id']}"
                )
            with col5:
                new_hat = st.checkbox(
                    f"hat ({row['player']})",
                    value=bool(row["hat"]) if row["hat"] else 0,
                    key=f"hat_edit_{row['player_id']}"
                )

            if st.button(f"Update {row['player']}", key=f"update_{row['player_id']}"):
                update_score(round_id, row["player_id"], new_score, new_birdies, new_eagles, new_hat)
                st.success(f"✅ Updated {row['player']}'s score")
elif menu == "Manage Players":
    st.subheader("Manage Players")

    # Add new player
    new_player = st.text_input("Add a new player")
    if st.button("➕ Add Player"):
        if new_player.strip():
            insert_player(new_player.strip())
            st.success(f"✅ Player '{new_player}' added!")
            st.rerun()
        else:
            st.warning("Please enter a valid name.")

    # List existing players
    players = load_players()
    if not players.empty:
        st.write("### Current Players")
        for _, row in players.iterrows():
            col1, col2 = st.columns([3, 1])
            col1.write(row["name"])
            if col2.button("❌ Delete", key=f"del_player_{row['player_id']}"):
                delete_player(row["player_id"])
                st.success(f"🗑️ Player '{row['name']}' deleted.")
                st.rerun()
    else:
        st.info("No players found.")
elif menu == "Manage Courses":
    st.subheader("Manage Courses")

    # Add new course
    new_course = st.text_input("Add a new course")
    if st.button("➕ Add Course"):
        if new_course.strip():
            insert_course(new_course.strip())
            st.success(f"✅ Course '{new_course}' added!")
            st.rerun()
        else:
            st.warning("Please enter a valid course name.")

    # List existing courses
    courses = load_courses()
    if not courses.empty:
        st.write("### Current Courses")
        for _, row in courses.iterrows():
            col1, col2 = st.columns([3, 1])
            col1.write(row["name"])
            if col2.button("❌ Delete", key=f"del_course_{row['course_id']}"):
                delete_course(row["course_id"])
                st.success(f"🗑️ Course '{row['name']}' deleted.")
                st.rerun()
    else:
        st.info("No courses found.")
