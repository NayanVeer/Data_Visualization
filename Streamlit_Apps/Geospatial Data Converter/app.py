import streamlit as st
import tempfile
import os
import zipfile
import csv
import pandas as pd
import rasterio
import fiona
from fiona import transform
from shapely.geometry import mapping, Point
import laspy

st.set_page_config(page_title="Geospatial Format Converter", layout="wide")
st.title("🌍 Geospatial Format Converter")

uploaded_file = st.file_uploader("Upload your geospatial file", type=None)

def is_raster(path):
    try:
        with rasterio.open(path) as src:
            return True
    except:
        return False

def is_vector(path):
    try:
        with fiona.open(path) as src:
            return True
    except:
        return False

def is_point_cloud(path):
    try:
        laspy.read(path)
        return True
    except:
        return False

def is_csv(path):
    return path.lower().endswith(".csv")

def convert_point_cloud(input_path, output_path, output_format):
    pc = laspy.read(input_path)
    if output_format == "csv":
        df = pd.DataFrame({'x': pc.x, 'y': pc.y, 'z': pc.z})
        df.to_csv(output_path, index=False)
    elif output_format in ["las", "laz"]:
        pc.write(output_path)

def csv_to_shapefile(csv_path, shp_folder, x_col='x', y_col='y'):
    shp_path = os.path.join(shp_folder, "points.shp")

    schema = {
        'geometry': 'Point',
        'properties': {}
    }

    df = pd.read_csv(csv_path)
    props = [col for col in df.columns if col not in [x_col, y_col]]
    for p in props:
        schema['properties'][p] = 'str'

    crs = 'EPSG:4326'
    with fiona.open(shp_path, 'w', driver='ESRI Shapefile', schema=schema, crs=crs) as layer:
        for _, row in df.iterrows():
            point = Point(row[x_col], row[y_col])
            properties = {p: str(row[p]) for p in props}
            layer.write({
                'geometry': mapping(point),
                'properties': properties
            })
    return shp_path

def zip_shapefile(shp_folder, zip_path):
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for ext in ['shp', 'shx', 'dbf', 'prj', 'cpg']:
            file = os.path.join(shp_folder, f"points.{ext}")
            if os.path.exists(file):
                zipf.write(file, arcname=f"points.{ext}")

if uploaded_file:
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, uploaded_file.name)
        with open(input_path, "wb") as f:
            f.write(uploaded_file.read())

        if is_vector(input_path):
            st.success("Vector file detected.")
            st.write("Currently vector conversions not supported without GDAL.")
        
        elif is_raster(input_path):
            st.success("Raster file detected.")
            st.write("Currently raster conversions not supported without GDAL.")

        elif is_point_cloud(input_path):
            st.success("Point cloud file detected.")
            options = ["csv", "las", "laz"]
            output_format = st.selectbox("Select output point cloud format", options)
            if st.button("Convert Point Cloud"):
                ext = output_format
                output_file = os.path.join(tmpdir, f"converted.{ext}")
                convert_point_cloud(input_path, output_file, output_format)
                with open(output_file, "rb") as f:
                    st.download_button("Download converted point cloud file", f, file_name=f"converted.{ext}")

        elif is_csv(input_path):
            st.success("CSV point data detected.")
            output_format = "ESRI Shapefile"
            if st.button("Convert CSV to Shapefile"):
                shp_folder = os.path.join(tmpdir, "shp_output")
                os.makedirs(shp_folder, exist_ok=True)
                shp_path = csv_to_shapefile(input_path, shp_folder)
                zip_path = os.path.join(tmpdir, "shapefile.zip")
                zip_shapefile(shp_folder, zip_path)
                with open(zip_path, "rb") as f:
                    st.download_button("Download Shapefile ZIP", f, file_name="shapefile.zip")

        else:
            st.error("Unsupported or corrupted file.")
