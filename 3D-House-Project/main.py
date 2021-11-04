import requests
import numpy as np
import pandas as pd
import json
import geopandas as gpd
import rioxarray
import rasterio
from rasterio import mask
import geojson
import matplotlib as plt
from matplotlib import pyplot as plt
import geopandas
from shapely.geometry import box
import georasters as gr
from osgeo import gdal
from rasterio.plot import show
import plotly.graph_objects as go
from shapely.geometry import Polygon
import shapefile


# Using an API to get the coordinates

address = input("Give an address: ")


def get_coordinates(address: str):
    
    req = requests.get(f"https://loc.geopunt.be/v4/Location?q={address}").json()
    info = {'address' : address, 
                'x_value' : req['LocationResult'][0]['Location']['X_Lambert72'],
                'y_value' : req['LocationResult'][0]['Location']['Y_Lambert72'],
                'street' : req['LocationResult'][0]['Thoroughfarename'],
                'house_number' : req['LocationResult'][0]['Housenumber'], 
                'postcode': req['LocationResult'][0]['Zipcode'], 
                'municipality' : req['LocationResult'][0]['Municipality']}
    
    detail = requests.get("https://api.basisregisters.vlaanderen.be/v1/adresmatch", 
                          params={"postcode": info['postcode'], 
                                  "straatnaam": info['street'],
                                  "huisnummer": info['house_number']}).json()
    building = requests.get(detail['adresMatches'][0]['adresseerbareObjecten'][0]['detail']).json()
    build = requests.get(building['gebouw']['detail']).json()
    info['polygon'] = [build['geometriePolygoon']['polygon']["coordinates"]]
    return info

info = get_coordinates(address)


# Read the bounds from the CSV

path = "ALL_BOUNDS.csv"
bounds = pd.read_csv(path) 


# X & Y are the longitude and latitude
# X = left & right, should be greater than the left and less than the right
# Y  = top & bottom , should be greater than bottom , less than top

# Find the coordinates in the bounds of the CSV file 
# For DSM

def find_coordinates_DSM():
    
    x = info["x_value"]
    y = info["y_value"]
    
    for num in range (0, 42+1):
        left_bounds = bounds.left[num]
        right_bounds = bounds.right[num]
        top_bounds = bounds.top[num]
        bottom_bounds = bounds.bottom[num]
        
        if x >= left_bounds and x <= right_bounds and y <= top_bounds and y >= bottom_bounds:
            DSM_tif = "Data/DSM/DSM-"+str(num+1)+"/GeoTIFF/DHMVIIDSMRAS1m_k"+("0" if num <= 8 else "")+str(num+1)+".tif"
            return DSM_tif
    
DSM_tif = find_coordinates_DSM()


# For DTM

def find_coordinates_DTM():
    
    x = info["x_value"]
    y = info["y_value"]
    
    for num in range (0, 42+1):
        
        left_bounds = bounds.left[num]
        right_bounds = bounds.right[num]
        top_bounds = bounds.top[num]
        bottom_bounds = bounds.bottom[num]
        
        if x >= left_bounds and x <= right_bounds and y <= top_bounds and y >= bottom_bounds:
            DTM_tif = "Data/DTM/DTM-"+str(num+1)+"/GeoTIFF/DHMVIIDTMRAS1m_k"+("0" if num <= 8 else "")+str(num+1)+".tif"
            return DTM_tif
            
            
DTM_tif = find_coordinates_DTM()

polygon = info["polygon"]


# Make the shapefile

def make_shapefile():
    
    write = shapefile.Writer("shapefiles/test/polygon")
    write.field("name", "C")
    write.poly([polygon[0][0]])
    write.record("polygon_1")
    write.close()
    
make_shapefile()

# Clip the shapefiles

polygon_path = "/home/becode/3D-House/3D-House-Project/shapefiles/test/polygon.shp"


# Clip DSM

def clip_DSM():
    
    OutTile = gdal.Warp("/home/becode/3D-House/3D-House-Project/shapefiles/test/DSM_clip2.tif", 
                    DSM_tif, 
                    cutlineDSName=polygon_path,
                    cropToCutline=True,
                    dstNodata = 0)
    OutTile = None 
    DSM_clip = rioxarray.open_rasterio("/home/becode/3D-House/3D-House-Project/shapefiles/test/DSM_clip2.tif", masked = True)
    return DSM_clip
    
DSM_clip = clip_DSM()


# Clip DTM

def clip_DTM():
    
    OutTile_2 = gdal.Warp("/home/becode/3D-House/3D-House-Project/shapefiles/test/DTM_clip2.tif", 
                          DTM_tif, 
                          cutlineDSName=polygon_path,
                          cropToCutline=True,
                          dstNodata = 0)
    OutTile_2 = None 
    DTM_clip = rioxarray.open_rasterio("/home/becode/3D-House/3D-House-Project/shapefiles/test/DTM_clip2.tif", masked = True)
    return DTM_clip

DTM_clip = clip_DTM()


# Calculate the CHM
# image is the CHM

image = DSM_clip - DTM_clip


# Clean the CHM by turning the NaN into zeros

def clean_image():
    
    new_image = np.where(np.isnan(image), 0, image)
    image_2 = np.pad(new_image[0], pad_width = 1, mode ="constant", constant_values = 0)
    return image_2

image_2 = clean_image()


# Show the final image

def show_imageshape():
    
    ab = image_2.shape[0]
    ac = image_2.shape[1]
    
    x, y = np.meshgrid(np.arange(ac), np.arange(ab))
    fig = plt.figure(figsize = (10, 10))
    
    ax = fig.add_subplot(projection="3d")
    ax.plot_surface(x, y, image_2)
    ax.set_zlim(0, 31)
    
    # Add some info
    
    ax.set_title(f"3D Building of {address}")
    ax.text2D(0.05, 0.95, f"Area = {int(x.max()*y.max())}m²", transform=ax.transAxes)
    ax.set_xlabel(f"Width = {x.max()}m")
    ax.set_ylabel(f"Length = {y.max()}m")
    ax.set_zlabel(f"Height = {int(image_2.max())}m")
    
    plt.show()
    
    # Figure 2
    
    fig = go.Figure(data=[go.Surface(z=image_2, x=x, y=y)])
    fig.update_layout(scene = dict(xaxis_title = f"Width = {x.max()}m",
                                  yaxis_title = f"Length = {y.max()}m",
                                  zaxis_title = f"Height = {int(image_2.max())}m"))
   
    
    fig.show()

show_imageshape()