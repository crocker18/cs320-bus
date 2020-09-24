#project: p2
#submitter: jrrichter2
#partner: cmdarling

from math import sin, cos, asin, sqrt, pi
from zipfile import ZipFile
import datetime
import pandas as pd
from graphviz import Graph, Digraph
import copy
import matplotlib
from matplotlib import pyplot as plt

def haversine_miles(lat1, lon1, lat2, lon2):
    """Calculates the distance between two points on earth using the
    harversine distance (distance between points on a sphere)
    See: https://en.wikipedia.org/wiki/Haversine_formula

    :param lat1: latitude of point 1
    :param lon1: longitude of point 1
    :param lat2: latitude of point 2
    :param lon2: longitude of point 2
    :return: distance in miles between points
    """
    lat1, lon1, lat2, lon2 = (a/180*pi for a in [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon/2) ** 2
    c = 2 * asin(min(1, sqrt(a)))
    d = 3956 * c
    return d


class Location:
    
    """Location class to convert lat/lon pairs to
    flat earth projection centered around capitol
    """
    capital_lat = 43.074683
    capital_lon = -89.384261

    def __init__(self, latlon=None, xy=None):
        if xy is not None:
            self.x, self.y = xy
        else:
            # If no latitude/longitude pair is given, use the capitol's
            if latlon is None:
                latlon = (Location.capital_lat, Location.capital_lon)

            # Calculate the x and y distance from the capital
            self.x = haversine_miles(Location.capital_lat, Location.capital_lon,
                                     Location.capital_lat, latlon[1])
            self.y = haversine_miles(Location.capital_lat, Location.capital_lon,
                                     latlon[0], Location.capital_lon)

            # Flip the sign of the x/y coordinates based on location
            if latlon[1] < Location.capital_lon:
                self.x *= -1

            if latlon[0] < Location.capital_lat:
                self.y *= -1

    def dist(self, other):
        """Calculate straight line distance between self and other"""
        return sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def __repr__(self):
        return "Location(xy=(%0.2f, %0.2f))" % (self.x, self.y)

def slicedatetime(date):
    
    date = str(date)
    year = int(date[0:4])
    month = int(date[4:6])
    day = int(date[6:])
    return datetime.datetime(year, month, day)

    
class BusDay:
    
    def __init__(self, date):
        
        #date attribute
        self.date = date
        
        #weekday attribute
        days = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
        self.weekday = days[date.weekday()]
        
        #service_ids attribute
        with ZipFile('mmt_gtfs.zip') as zf:
            with zf.open("calendar.txt") as f:
                caldf = pd.read_csv(f)
                
        servicedf = caldf[caldf[self.weekday] == 1]
        
        servicedf = servicedf[servicedf["start_date"].apply(slicedatetime) <= self.date]
        servicedf = servicedf[servicedf["end_date"].apply(slicedatetime) >= self.date]
        
        servicelist = list(servicedf["service_id"])
        servicelist.sort()
        
        self.service_ids = servicelist
        
        self.splitter()
        
    def get_trips(self, route=None):
        trip_list = []
        with ZipFile('mmt_gtfs.zip') as zf:
            with zf.open("trips.txt") as f:
                trips_df = pd.read_csv(f)
        if route != None:
            trips_df = trips_df[trips_df["route_short_name"] == route]
        trips_df = trips_df[trips_df["service_id"].isin(self.service_ids)]
        for index, row in trips_df.iterrows():
            current_trip = Trip(row["trip_id"], row["route_short_name"], bool(row["bikes_allowed"]))
            trip_list.append(current_trip)
        trip_list.sort()
        return trip_list
    
    def get_stops(self):
        stop_list = []
        with ZipFile('mmt_gtfs.zip') as zf:
            with zf.open("stops.txt") as f:
                stops_df = pd.read_csv(f)
        with ZipFile('mmt_gtfs.zip') as zf:
            with zf.open("stop_times.txt") as f:
                stop_times_df = pd.read_csv(f)     
        
        s = list(pd.Series(f.trip_id for f in self.get_trips()))
        
        day_stop_times_df = stop_times_df[stop_times_df["trip_id"].isin(s)]
        day_stops_set = set(day_stop_times_df["stop_id"])
        
        day_stops_df = stops_df[stops_df["stop_id"].isin(day_stops_set)]
        
        for index, row in day_stops_df.iterrows():
            current_stop = Stop(row["stop_id"], Location(latlon = (row["stop_lat"], row["stop_lon"])),       
                                bool(row["wheelchair_boarding"]))
            stop_list.append(current_stop)
        stop_list.sort()
        return stop_list
    
    def range_query(self, node, x, y, results = None):
        
        range_query = self.range_query
        if results == None:
            results = []
            nodecount = 0
      
        if node.level < 6:
            
            if node.level % 2 == 0:
                if x[0] <= node.median.loc.x and x[1] >= node.stops[0].loc.x:
                    results = range_query(node.left, x, y, results)
                if  x[1] >= node.median.loc.x and x[0] <= node.stops[-1].loc.x:
                    results = range_query(node.right, x, y, results)
            else:
                if y[0] <= node.median.loc.y and y[1] >= node.stops[0].loc.y:
                    results = range_query(node.left, x, y, results)
                if y[1] >= node.median.loc.y and y[0] <= node.stops[-1].loc.y:
                    results = range_query(node.right, x, y, results)
                        
        if node.level == 6:
            addlist = []
            for i in node.stops:
                if x[0] <= i.loc.x <= x[1]:
                    if  y[0] <= i.loc.y <= y[1]:
                        addlist.append(i)
            new = results + addlist
            return new
        return results
        
    def get_stops_rect(self, x, y):
           
        rectlist = self.range_query(self.root, x, y)
        return rectlist
        
    def get_stops_circ(self, center, radius):
        x0 = center[0] - radius
        x1 = center[0] + radius
        y0 = center[1] - radius
        y1 = center[1] + radius
        x = (x0, x1)
        y = (y0, y1)
        framed = self.get_stops_rect(x, y)
        circlist = []
        for i in framed:
            diffx = i.loc.x - center[0]
            diffy = i.loc.y - center[1]
            dist = sqrt((diffx**2) + (diffy**2))
            if dist <= radius:
                circlist.append(i)
        return circlist
    
    def splitter(self, parent = None):
        
        if parent == None:
            parent = Node(self.get_stops())
            self.root = parent
            self.todo = []
            self.repcount = 0
            parent.stops.sort(key=lambda cur_stops: cur_stops.loc.x)
        cur_stops = parent.stops
        if parent.level != 6:
            if parent.level % 2 == 0: #x split
                cur_stops.sort(key=lambda cur_stops: cur_stops.loc.x)
                parent.right = Node(cur_stops[len(cur_stops)//2:])
                parent.left = Node(cur_stops[:len(cur_stops)//2])
                parent.left.level = parent.level + 1
                parent.right.level = parent.level + 1
                parent.median = cur_stops[len(cur_stops)//2:][0]

            if parent.level % 2 == 1: #y split
                cur_stops.sort(key=lambda cur_stops: cur_stops.loc.y)
                parent.right = Node(cur_stops[len(cur_stops)//2:])
                parent.left = Node(cur_stops[:len(cur_stops)//2])
                parent.left.level = parent.level + 1
                parent.right.level = parent.level + 1
                parent.median = cur_stops[len(cur_stops)//2:][0]
                
            # just some code to make the output easier to read
            parent.left.rep = self.repcount + 0
            self.repcount+=1
            parent.right.rep = self.repcount + 0
            self.repcount+=1
            # end of unnecessary code
            
            self.todo.append(parent.left)
            self.todo.append(parent.right)

        if len(self.todo) == 0:
            
            return None
        
        self.splitter(self.todo.pop(0))
        
    def get_ax(self):
        ax = plt.subplot()
        ax.spines['left'].set_position('zero')
        ax.spines['bottom'].set_position('zero')
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        return ax
   
    def scatter_stops(self, ax=None):
        stops = self.get_stops()
        if ax == None:
            ax = self.get_ax()
        x_coords_i = []
        y_coords_i = []
        for stop in stops:
            if stop.wheelchair_boarding == True:
                x_coords_i.append(stop.loc.x)
                y_coords_i.append(stop.loc.y)
    
        dict_true = {"x": x_coords_i, "y": y_coords_i}
        df_i = pd.DataFrame(dict_true)
        
        x_coords_ii = []
        y_coords_ii = []
        for stop in stops:
            if stop.wheelchair_boarding == False:
                x_coords_ii.append(stop.loc.x)
                y_coords_ii.append(stop.loc.y)
    
        dict_false = {"x": x_coords_ii, "y": y_coords_ii}
        df_ii = pd.DataFrame(dict_false)
        
        df_i.plot.scatter("x", "y", s=2, color="red", ax=ax, marker = 'o', xlim=(-8,8), ylim=(-8,8), figsize=(8,8))
        df_ii.plot.scatter("x", "y", s=2, color="0.7", ax=ax, marker = 'o', xlim=(-8,8), ylim=(-8,8), figsize=(8,8))
        return ax
    
    def draw_tree(self, ax=None, level=0, parent=None, min_val_x=-8, min_val_y=-8, max_val_x=8, max_val_y=8):
        if ax == None:
            ax = self.get_ax()
        if level == 0:
            parent = self.root
        if parent.median != None:
            current_split = parent.median
            current_split_x = current_split.loc.x
            current_split_y = current_split.loc.y
        if level < 6:
            if (level % 2 == 0):
                ax.plot((current_split_x, current_split_x), (min_val_x, max_val_x), lw=(7-level), color="lightgreen", zorder=0)
                self.draw_tree(ax=ax, level=level+1, parent=parent.right, min_val_y=current_split_x, max_val_y=max_val_y, min_val_x=min_val_x, max_val_x=max_val_x)
                self.draw_tree(ax=ax, level=level+1, parent=parent.left, min_val_y=min_val_y, max_val_y=current_split_x, min_val_x=min_val_x, max_val_x=max_val_x)
            else:
                ax.plot((min_val_y, max_val_y), (current_split_y, current_split_y), lw=(7-level), color="lightgreen", zorder=0)
                self.draw_tree(ax=ax, level=level+1, parent=parent.right, min_val_x=current_split_y , max_val_x=max_val_x, min_val_y=min_val_y, max_val_y=max_val_y)
                self.draw_tree(ax=ax, level=level+1, parent=parent.left, min_val_x=min_val_x, max_val_x=current_split_y, min_val_y=min_val_y, max_val_y=max_val_y)
        return ax
    
class Node: # adapted from CS 320 lecture 11 notes; instructor: Tyler Caraza-Harter, UW-Madison, Spring 2020
    
    def __init__(self, stops):
        self.stops = stops
        self.left = None
        self.right = None
        self.level = 0
        self.val = 0
        self.rep = None
        self.median = None
        
    def to_graphviz(self, g=None):
        if g == None:
            g = Digraph()
            
        # draw self
        g.node(repr(self.rep))
    
        for label, child in [("L", self.left), ("R", self.right)]:
            if child != None:
                # draw child, recursively
                child.to_graphviz(g)
                
                # draw edge from self to child
                g.edge(repr(self.rep), repr(child.rep), label=label)
        return g
    
    def _repr_svg_(self):
        return self.to_graphviz()._repr_svg_()
    
        
class Stop:
    
    def __init__(self, stop_id, loc, wheelchair):
        self.stop_id= stop_id
        self.loc = loc
        self.wheelchair_boarding = bool(wheelchair)
    
    def __repr__(self):
        s = "Stop({}, {}, {})"
        return s.format(repr(self.stop_id), repr(self.loc), repr(self.wheelchair_boarding))
    
    def __lt__(self, other):
        return self.stop_id < other.stop_id
                                
class Trip:
    
    def __init__(self, trip_id, route_id, bikes_allowed):
        self.trip_id = trip_id
        self.route_id = route_id
        self.bikes_allowed = bikes_allowed

    def __repr__(self):
        s = "Trip({}, {}, {})"
        return s.format(repr(self.trip_id), repr(self.route_id), repr(self.bikes_allowed))
    
    def __lt__(self, other):
        return self.trip_id < other.trip_id
        









