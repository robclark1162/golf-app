import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client, Client
import os

# --- Supabase Connection ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://aqaiziylxougtlaihlor.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFxYWl6aXlseG91Z3RsYWlobG9yIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTgxNjk1NTMsImV4cCI6MjA3Mzc0NTU1M30.kqhyv4WIFw0SQUoNocX_8TNXouVm4XUzIGO2FY0nhVY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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
        score_id,
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


# --- Streamlit UI Placeholder (rest of your Golf_App.py UI remains unchanged) ---
#st.title("🏌️ Golf Twitchers Competition Tracker (Supabase)")

#menu = st.sidebar.radio("Menu", ["View Scores", "Summary", "Scores by Day", "Add Round", "Edit Round", "Manage Players", "Manage Courses"])

# The rest of your UI code (summary, add/edit round, etc.) will continue to work with these new Supabase helpers.

# --- Cap code
# --- helper: convert image to base64 ---
#def get_base64_image(image_path):
 #   with open(image_path, "rb") as f:
 #       data = f.read()
 #   return base64.b64encode(data).decode()

# load red cap once at the top
#redcap_base64 = get_base64_image("red_cap.png")
#hat_icon = f'<img src="data:image/png;base64,{redcap_base64}" width="20"/>'
# --- Streamlit UI ---
st.title("🏌️ Golf Trwitchers Competition Tracker")

menu = st.sidebar.radio(
    "Menu",
    ["View Scores", "Summary", "Scores by Day", "Add Round", "Edit Round", "Manage Players", "Manage Courses"]
)


# --- View Scores ---
if menu == "View Scores":
    st.subheader("All Scores")
    df = load_scores()
    st.dataframe(df, width= 'content')

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
            st.dataframe(scores_pivot.style.format(fmt_scores), use_container_width=True)

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
            st.dataframe(birdies_table.style.format(fmt_bird), use_container_width=True)

            st.markdown("### Eagles")
            st.dataframe(eagles_table.style.format(fmt_eag), use_container_width=True)

elif menu == "Summary": 
    st.subheader("Player Summary")
    df = load_scores()

    if df.empty:
        st.info("No scores available yet.")
    else:
        # --- Add filter date ---
        min_date = pd.to_datetime(df["round_date"]).min().date()
        start_date = st.date_input("📅 Only include scores after:", value=min_date, min_value=min_date)

        # Filter data
        df = df[pd.to_datetime(df["round_date"]) >= pd.to_datetime(start_date)]

        if df.empty:
            st.warning("No scores found after selected date.")
        else:
            # --- Minimum rounds filter ---
            min_rounds = st.number_input("Minimum rounds required", min_value=1, max_value=20, value=6, step=1)

            # Count rounds per player
            rounds_count = df.groupby("player")["round_date"].nunique().reset_index()
            rounds_count.columns = ["player", "rounds_played"]

            # Keep only eligible players
            eligible_players = rounds_count[rounds_count["rounds_played"] >= min_rounds]["player"]
            df = df[df["player"].isin(eligible_players)]

            if df.empty:
                st.warning(f"No players found with at least {min_rounds} rounds after {start_date}.")
            else:
                summary = {}
                players = sorted(df["player"].unique())

                # --- Find single latest hat-holder ---
                hat_rounds = df[df["hat"] == True]
                hat_holder = None
                if not hat_rounds.empty:
                    latest_hat = hat_rounds.loc[hat_rounds["round_date"].idxmax()]
                    hat_holder = latest_hat["player"]

                for player in players:
                    ps = df[df["player"] == player].sort_values("round_date")
                    times_played = len(ps)
                    if times_played == 0:
                        continue

                    # --- Last score, trend ---
                    last_score = ps.iloc[-1]["score"]

                    if times_played > 1:
                        prev_score = ps.iloc[-2]["score"]
                        if last_score > prev_score:
                            trend = "<span style='color:green'>▲</span>"
                        elif last_score < prev_score:
                            trend = "<span style='color:red'>▼</span>"
                        else:
                            trend = "<span style='color:grey'>→</span>"
                    else:
                        trend = ""

                    # --- Add red cap only if this is the single latest hat-holder ---
                    display_name = player
                    if hat_holder == player:
                        display_name += f" {}"

                    avg_score = ps["score"].mean()
                    best_round = ps["score"].max()
                    worst_round = ps["score"].min()
                    best6 = ps["score"].nlargest(6).mean() if times_played >= 6 else ps["score"].mean()
                    worst6 = ps["score"].nsmallest(6).mean() if times_played >= 6 else ps["score"].mean()

                    # --- Birdies, Eagles, Hats totals ---
                    total_birdies = ps["birdies"].sum()
                    total_eagles = ps["eagles"].sum()
                    total_hats = ps["hat"].sum()

                    summary[display_name] = {
                        "Times Played": times_played,
                        "Last Score": f"{int(last_score)} {trend}",
                        "Average": avg_score,
                        "Best Round": int(best_round),
                        "Worst Round": int(worst_round),
                        "Avg best 6": best6,
                        "Avg worst 6": worst6,
                        "Total Birdies": total_birdies,
                        "Total Eagles": total_eagles,
                        "Total Hats": total_hats
                    }

                summary_df = pd.DataFrame(summary).T

                # ---- ranks (Stableford: higher is better) ----
                summary_df["Avg Rank"] = summary_df["Average"].rank(ascending=False, method="min")
                summary_df["Best Round Rank"] = summary_df["Best Round"].rank(ascending=False, method="min")
                summary_df["Worst Round Rank"] = summary_df["Worst Round"].rank(ascending=False, method="min")
                summary_df["Rank Best 6"] = summary_df["Avg best 6"].rank(ascending=False, method="min")
                summary_df["Rank Worst"] = summary_df["Avg worst 6"].rank(ascending=False, method="min")

                # ---- numeric formatting ----
                for col in ["Average", "Avg best 6", "Avg worst 6"]:
                    summary_df[col] = pd.to_numeric(summary_df[col], errors="coerce").round(2)

                rank_cols = ["Avg Rank", "Best Round Rank", "Worst Round Rank", "Rank Best 6", "Rank Worst"]
                for col in rank_cols:
                    summary_df[col] = pd.to_numeric(summary_df[col], errors="coerce").astype("Int64")

                summary_df = summary_df.reset_index().rename(columns={"index": "Player"})
                cols_order = [
                    "Player", "Times Played", "Last Score", "Average", "Avg Rank",
                    "Best Round", "Best Round Rank", "Worst Round", "Worst Round Rank",
                    "Avg best 6", "Rank Best 6", "Avg worst 6", "Rank Worst",
                    "Total Birdies", "Total Eagles", "Total Hats"
                ]
                summary_df = summary_df[cols_order]

                styled_summary = (
                    summary_df.style
                    .apply(lambda row: [highlight_ranks(v, col) for v, col in zip(row, summary_df.columns)], axis=1)
                    .format({
                        "Average": "{:.2f}",
                        "Avg best 6": "{:.2f}",
                        "Avg worst 6": "{:.2f}",
                        "Avg Rank": "{:.0f}",
                        "Best Round Rank": "{:.0f}",
                        "Worst Round Rank": "{:.0f}",
                        "Rank Best 6": "{:.0f}",
                        "Rank Worst": "{:.0f}"
                    })
                    .to_html(escape=False)
                )

                st.markdown(f"<div style='overflow-x:auto; width:160%'>{styled_summary}</div>", unsafe_allow_html=True)


# --- Add Round ---
elif menu == "Add Round":
    st.subheader("Add a New Round")

    round_date = st.date_input("Date", value=date.today())
    courses = load_courses()
    course = st.selectbox("Course", courses["name"])
    course_id = int(courses[courses["name"] == course]["course_id"].iloc[0])

    players = load_players()
   # st.write("DEBUG players:", type(players))
    #st.write(players.head())
    scores = {}

    st.markdown("### Enter Scores")

    for _, row in players.iterrows():
        st.markdown(f"**{row['name']}**")
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])  # adjust widths

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
            st.experimental_rerun()
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
                st.experimental_rerun()
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
            st.experimental_rerun()
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
                st.experimental_rerun()
    else:
        st.info("No courses found.")
