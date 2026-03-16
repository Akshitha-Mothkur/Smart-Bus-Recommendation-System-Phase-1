import re
import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Smart Bus Route",
    page_icon="🚌",
    layout="centered"
)

# ------------------------------------------------
# CUSTOM CSS
# ------------------------------------------------

st.markdown("""
<style>

body {background:#0b1220;color:#f8fafc;}
.stApp {background:#0b1220;}

.bus-card{
  background:#111827;
  padding:18px;
  border-radius:14px;
  margin-bottom:18px;
  border:1px solid rgba(255,255,255,0.12);
  box-shadow:0 10px 18px rgba(0,0,0,0.5);
}

.best-card{
  border:2px solid #16a34a;
  box-shadow:0 0 0 2px rgba(22,163,74,0.35);
}

.bus-header{
  font-weight:700;
  font-size:18px;
}

.route-text{
  font-weight:600;
  font-size:16px;
  color:#f1f5f9;
}

.time{
  font-weight:600;
  font-size:15px;
}

.info{
  color:#cbd5e1;
  font-size:15px;
}

.class-tag{
  background:#1f2937;
  padding:3px 8px;
  border-radius:6px;
  font-size:13px;
  margin-left:8px;
}

</style>
""", unsafe_allow_html=True)

# ------------------------------------------------
# LOAD DATA
# ------------------------------------------------

@st.cache_data
def load_data():
    """
    CSV is loaded once and cached.
    Streamlit will not reload it every interaction.
    """

    df = pd.read_csv("full_data.csv", engine="python", on_bad_lines="skip")

    df.columns = df.columns.str.strip()

    df = df.dropna(subset=["trip_id","stop_name"])

    return df


# ------------------------------------------------
# BUILD STOP INDEX
# ------------------------------------------------

@st.cache_data
def build_stop_index(df):
    """
    stop_name → rows for that stop

    Instead of scanning full dataframe every query,
    we directly access rows belonging to that stop.

    Complexity improvement:
    OLD  : O(N)
    NEW  : O(1) lookup
    """

    stop_index = {}

    grouped = df.groupby("stop_name")

    for stop, group in grouped:
        stop_index[stop] = group

    return stop_index


# ------------------------------------------------
# BUILD TRIP INDEX
# ------------------------------------------------

@st.cache_data
def build_trip_index(df):
    """
    trip_id → ordered trip dataframe

    Each trip contains all its stops sorted by stop_sequence.

    This allows fast lookup inside a trip without merge().
    """

    trip_index = {}

    grouped = df.sort_values("stop_sequence").groupby("trip_id")

    for trip_id, group in grouped:
        trip_index[trip_id] = group

    return trip_index


# ------------------------------------------------
# TIME UTILS
# ------------------------------------------------

def time_to_seconds(t):
    return t.hour*3600 + t.minute*60


def seconds_to_time(sec):

    sec = sec % 86400

    h = sec//3600
    m = (sec%3600)//60

    return f"{h:02d}:{m:02d}"


# ------------------------------------------------
# FAST ROUTE SEARCH
# ------------------------------------------------

# ------------------------------------------------
# PREFER SHORT WAIT / NEAR-TERM BUSES
# ------------------------------------------------

# Maximum allowed wait time (minutes) to consider a bus in recommendations.
# This prevents suggesting buses that depart too far into the future.
MAX_WAIT_MIN = 20

# Only consider buses departing within this many minutes from now.
# Helps ensure we recommend a bus that is imminent.
MAX_LOOKAHEAD_MIN = 50


def find_valid_trips(stop_index, trip_index, source, destination, current_sec):

    """
    FAST ROUTE SEARCH ALGORITHM

    Instead of merging large dataframes,
    we check only trips that visit the source stop.

    Steps
    -----

    1. Get rows of source stop
    2. For each trip passing source
    3. Check if destination appears later
    4. Compute travel + wait time

    Complexity roughly:

    O(K)

    where K = trips passing the source stop
    """

    if source not in stop_index:
        return pd.DataFrame()

    src_rows = stop_index[source]

    results = []

    for _, row in src_rows.iterrows():

        trip_id = row["trip_id"]

        trip = trip_index[trip_id]

        dest_rows = trip[
            (trip["stop_name"] == destination) &
            (trip["stop_sequence"] > row["stop_sequence"])
        ]

        if dest_rows.empty:
            continue

        dest = dest_rows.iloc[0]

        dep_sec = row["dep_sec"]
        arr_sec = dest["arr_sec"]

        wait = (dep_sec - current_sec) / 60

        # Ignore buses that have already departed
        if wait < 0:
            continue

        # Keep recommendations within a near-term window
        if wait > MAX_LOOKAHEAD_MIN or wait > MAX_WAIT_MIN:
            continue

        travel = ((arr_sec - dep_sec) % 86400) / 60

        results.append({
            "Bus": row["route_short_name"],
            "Trip": row["trip_headsign"],
            "Bus_Class": row.get("bus_class",""),
            "Stops": dest["stop_sequence"] - row["stop_sequence"],
            "Wait_min": wait,
            "Duration_min": travel,
            "Total_min": wait + travel,
            "Board_Time": seconds_to_time(dep_sec),
            "Reach_Time": seconds_to_time(arr_sec)
        })

    df = pd.DataFrame(results)

    if df.empty:
        return df

    # Sort properly
    df = df.sort_values(["Total_min","Wait_min"])

    # Remove duplicate buses
    df = df.drop_duplicates(subset=["Bus"], keep="first")

    return df.head(5)


# ------------------------------------------------
# BEST BUS
# ------------------------------------------------

def choose_best_bus(df):

    best = df.iloc[0]

    for i in range(1,len(df)):

        alt = df.iloc[i]

        diff = alt["Total_min"] - best["Total_min"]

        if diff <= 5 and alt["Wait_min"] < best["Wait_min"]:
            best = alt

    return best


# ------------------------------------------------
# BUS CARD UI
# ------------------------------------------------

def bus_card(bus, best=False):

    card_class = "bus-card best-card" if best else "bus-card"

    trip_text = re.sub(r"<[^>]+>", "", str(bus.get("Trip","")))

    st.markdown(f"""
    <div class="{card_class}">
    
    <div class="bus-header">
        🚌 Bus {bus['Bus']}
        <span class="class-tag">{bus['Bus_Class']}</span>
    </div>

    <div class="route-text">{trip_text}</div>

    <br>

    <div class="time">
    🟢 Board at: {bus['Board_Time']} <br>
    🔴 Reach by: {bus['Reach_Time']}
    </div>

    <br>

    <div class="info">
    ⏱ Total Trip: {round(bus['Total_min'])} min <br>
    🚏 Stops: {bus['Stops']} &nbsp;&nbsp;
    ⏱ Travel: {round(bus['Duration_min'])} min &nbsp;&nbsp;
    ⌛ Wait: {int(bus['Wait_min'])} min
    </div>

    </div>
    """, unsafe_allow_html=True)


# ------------------------------------------------
# MAIN APP
# ------------------------------------------------

def main():

    st.title("🚌 Smart Bus Route Recommendation")
    st.caption("Using TSRTC transit data")

    df = load_data()

    stop_index = build_stop_index(df)

    trip_index = build_trip_index(df)

    stops = sorted(stop_index.keys())

    with st.form(key="search_form"):
        source = st.selectbox("Source Stop", stops)

        destination = st.selectbox("Destination Stop", stops)

        current_time = st.time_input("Current Time")

        submit = st.form_submit_button("Find Buses")

    if submit:
        current_sec = time_to_seconds(current_time)

        valid = find_valid_trips(
            stop_index,
            trip_index,
            source,
            destination,
            current_sec
        )

        if valid.empty:
            st.error(f"No buses available within {MAX_WAIT_MIN} min wait window. Try a different time or route.")
            return

        best = choose_best_bus(valid)

        st.subheader("⭐ Best Option")

        bus_card(best, True)

        st.subheader("Next Available Buses")

        for i, row in valid.iterrows():

            if i != best.name:
                bus_card(row)


# ------------------------------------------------

if __name__ == "__main__":
    main()