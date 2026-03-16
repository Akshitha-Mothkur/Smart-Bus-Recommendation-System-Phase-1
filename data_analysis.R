#list of all bus routes
routes=read.csv("yourpath\\routes.csv")

nrow(routes)
ncol(routes)
colnames(routes)
str(routes)
head(routes)
View(routes)
#This dataset has no missing values


#trips.csv
#each record shows complete info about 1 trip
trips=read.csv("yourpath\\trips.csv")
View(trips)
nrow(trips)
colnames(trips)
ncol(trips)
str(trips)
head(trips)


#stop_times
stop_times=read.csv("yourpath\\stop_times.csv")
colnames(stop_times)
nrow(stop_times)
str(stop_times)
head(stop_times)
View(stop_times)


#stops.csv 
#geographical info about stops 
stops <- read.csv("yourpath\\stops.csv")
View(stops)
nrow(stops)
ncol(stops)
colnames(stops)
str(stops)
head(stops)
colSums(is.na(routes))
colSums(is.na(trips))
colSums(is.na(stop_times))
colSums(is.na(stops))
library(dplyr)




# unique entities
length(unique(routes$route_id))
length(unique(trips$trip_id))
length(unique(stops$stop_id))


#load libraries
library(dplyr)
library(ggplot2)
library(lubridate)
library(stringr)

#trips per route
trips_per_route <- trips %>%
  group_by(route_id) %>%
  summarise(total_trips = n())

ggplot(trips_per_route, aes(x=total_trips)) +
  geom_histogram(bins=30, fill="orange") +
  ggtitle("Trips per Route Distribution") +
  xlab("Number of Trips")

#bus class distribution
ggplot(trips, aes(x=bus_class)) +
  geom_bar(fill="darkgreen") +
  theme(axis.text.x = element_text(angle=45)) +
  ggtitle("Distribution of Bus Classes")

ggplot(trips, aes(x=depot)) +
  geom_bar(fill="purple") +
  theme(axis.text.x = element_text(angle=90)) +
  ggtitle("Trips Operated by Depot")
depot_trips <- trips %>%
  group_by(depot) %>%
  summarise(total_trips = n()) %>%
  arrange(desc(total_trips))

depot_trips

major_depots <- depot_trips %>%
  top_n(5, total_trips)

major_depots
minor_depots <- depot_trips %>%
  arrange(total_trips) %>%
  head(5)

minor_depots

stops_per_trip <- stop_times %>%
  group_by(trip_id) %>%
  summarise(total_stops = n())

ggplot(stops_per_trip, aes(x=total_stops)) +
  geom_histogram(bins=40, fill="skyblue") +
  ggtitle("Number of Stops per Trip")


#Important feature derivation => Trip duration


convert_to_seconds <- function(time){
  parts <- strsplit(time, ":")
  sapply(parts, function(x){
    as.numeric(x[1])*3600 + as.numeric(x[2])*60 + as.numeric(x[3])
  })
}

stop_times$dep_sec <- convert_to_seconds(stop_times$departure_time)
stop_times$arr_sec <- convert_to_seconds(stop_times$arrival_time)
trip_duration <- stop_times %>%
  group_by(trip_id) %>%
  summarise(
    start_time = min(dep_sec),
    end_time = max(arr_sec)
  ) %>%
  mutate(duration = (end_time - start_time)/60)
stop_times <- stop_times %>%
  arrange(trip_id, stop_sequence)

stop_times <- stop_times %>%
  group_by(trip_id) %>%
  mutate(
    next_time = lead(arr_sec),
    segment_duration = (next_time - arr_sec)/60
  )
ggplot(trip_duration, aes(x=duration)) +
  geom_histogram(bins=50, fill="red") +
  ggtitle("Distribution of Trip Durations") +
  xlab("Trip Duration (minutes)")
ggplot(stop_times, aes(x=segment_duration)) +
  geom_histogram(bins=40, fill="purple") +
  ggtitle("Travel Time Between Consecutive Stops")


full_data <- stop_times %>%
  left_join(trips, by = "trip_id") %>%
  left_join(routes, by = "route_id") %>%
  left_join(stops, by = "stop_id")
str(full_data)
head(full_data,3)
View(full_data)
#cleaning and processing 
full_data$trip_headsign <- trimws(full_data$trip_headsign)
full_data$trip_headsign <- sub("^[^ ]+ ", "", full_data$trip_headsign)
full_data$trip_headsign[1:2]

full_data$origin <- sub(" to.*", "", full_data$trip_headsign)
full_data$destination <- sub(".* to ", "", full_data$trip_headsign)
full_data <- full_data %>%
  select(
    trip_id,
    route_id,
    route_short_name,   # bus number
    
    depot,
    bus_class,
    
    stop_id,
    stop_name,
    stop_sequence,
    
    departure_time,
    arrival_time,
    dep_sec,
    arr_sec,
    
    segment_duration,
    
    origin,
    destination,
    trip_headsign
  )
colnames(full_data)
nrow(full_data)
ncol(full_data)
full_data <- distinct(full_data)

#example walk through 
src <- full_data %>%
  filter(stop_name == "Moosarambhagh")

dest <- full_data %>%
  filter(stop_name == "Ramnagar X Roads")

possible_trips <- inner_join(src, dest, by="trip_id", suffix=c(".src",".dest"))

current_time_sec <- 8*3600 + 10*60

valid_trips <- possible_trips %>%
  filter(stop_sequence.src < stop_sequence.dest) %>%
  mutate(
    stops_between = stop_sequence.dest - stop_sequence.src,
    duration = (arr_sec.dest - dep_sec.src) / 60,
    wait_time = (dep_sec.src - current_time_sec) / 60
  ) %>%
  filter(wait_time >= 0 & wait_time <= 60)

best_buses <- valid_trips %>%
  mutate(
    Bus_Arrives = format(as.POSIXct(dep_sec.src, origin="1970-01-01", tz="UTC"), "%H:%M"),
    Reach_Destination = format(as.POSIXct(arr_sec.dest, origin="1970-01-01", tz="UTC"), "%H:%M"),
    Duration_min = round(duration),
    Wait_min = round(wait_time)
  ) %>%
  select(
    route_short_name.src,
    trip_headsign.src,
    stops_between,
    Duration_min,
    Wait_min,
    Bus_Arrives,
    Reach_Destination
  ) %>%
  rename(
    Bus = route_short_name.src,
    Trip = trip_headsign.src,
    Stops = stops_between
  )
best_buses <- best_buses %>% ungroup()
best_buses <- best_buses %>%
  arrange(Reach_Destination)
View(best_buses)
head(best_buses,3)

write.csv(full_data, "yourpath\\full_data.csv", row.names = FALSE)
