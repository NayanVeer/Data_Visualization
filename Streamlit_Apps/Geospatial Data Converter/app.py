import streamlit as st
import tempfile
import os
import zipfile
import csv
from pathlib import Path
from osgeo import gdal, ogr, osr
import laspy

st.set_page_config(page_title="Geospatial Format Converter", layout="wide")
st.title("🌍 Geospatial Format Converter")

uploaded_file = st.file_uploader("Upload your geospatial file", type=None)

def is_raster(path):
    try:
        return gdal.Open(path) is not None
    except:
        return False

def is_vector(path):
    try:
        ds = ogr.Open(path)
        return ds is not None and ds.GetLayerCount() > 0
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

def convert_vector(input_path, output_path, output_format):
    driver_map = {
        "GeoJSON": ("GeoJSON", "geojson"),
        "GPKG": ("GPKG", "gpkg"),
        "ESRI Shapefile": ("ESRI Shapefile", "shp"),
        "KML": ("KML", "kml"),
    }
    driver_name, ext = driver_map[output_format]

    driver = ogr.GetDriverByName(driver_name)
    if os.path.exists(output_path):
        driver.DeleteDataSource(output_path)

    ds = ogr.Open(input_path)
    layer = ds.GetLayer()

    out_ds = driver.CreateDataSource(output_path)
    out_layer = out_ds.CreateLayer(layer.GetName(), geom_type=layer.GetGeomType())

    # Copy fields
    layer_defn = layer.GetLayerDefn()
    for i in range(layer_defn.GetFieldCount()):
        field_defn = layer_defn.GetFieldDefn(i)
        out_layer.CreateField(field_defn)

    out_defn = out_layer.GetLayerDefn()

    # Copy features
    for feat in layer:
        out_feat = ogr.Feature(out_defn)
        out_feat.SetGeometry(feat.GetGeometryRef())
        for i in range(out_defn.GetFieldCount()):
            out_feat.SetField(out_defn.GetFieldDefn(i).GetNameRef(), feat.GetField(i))
        out_layer.CreateFeature(out_feat)
        out_feat = None

    out_ds = None
    ds = None

def convert_raster(input_path, output_path, output_format):
    format_map = {
        "GTiff": "GTiff",
        "COG": "COG",
        "JPEG": "JPEG",
        "PNG": "PNG",
    }
    fmt = format_map[output_format]
    gdal.Translate(output_path, input_path, format=fmt)

def convert_point_cloud(input_path, output_path, output_format):
    pc = laspy.read(input_path)
    if output_format == "csv":
        with open(output_path, "w") as f:
            f.write("x,y,z\n")
            for x, y, z in zip(pc.x, pc.y, pc.z):
                f.write(f"{x},{y},{z}\n")
    elif output_format in ["las", "laz"]:
        pc.write(output_path)

def csv_to_shp(csv_path, shp_folder, x_col='x', y_col='y'):
    """
    Convert CSV points to ESRI Shapefile (outputs multiple files in shp_folder).
    """
    shp_path = os.path.join(shp_folder, "points.shp")
    driver = ogr.GetDriverByName("ESRI Shapefile")
    if os.path.exists(shp_path):
        driver.DeleteDataSource(shp_path)

    ds = driver.CreateDataSource(shp_path)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)  # WGS84, change if needed
    layer = ds.CreateLayer("points", srs, ogr.wkbPoint)

    # Add fields for other CSV columns besides x,y
    with open(csv_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        fieldnames = reader.fieldnames
        # Remove x and y from attributes
        attr_fields = [f for f in fieldnames if f.lower() not in [x_col.lower(), y_col.lower()]]

        # Create attribute fields
        for attr in attr_fields:
            layer.CreateField(ogr.FieldDefn(attr, ogr.OFTString))

        layer_defn = layer.GetLayerDefn()

        for row in reader:
            x = float(row[x_col])
            y = float(row[y_col])
            point = ogr.Geometry(ogr.wkbPoint)
            point.SetPoint_2D(0, x, y)

            feature = ogr.Feature(layer_defn)
            feature.SetGeometry(point)
            for attr in attr_fields:
                feature.SetField(attr, row[attr])
            layer.CreateFeature(feature)
            feature = None

    ds = None
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
            st.success("Vector data detected.")
            options = ["GeoJSON", "GPKG", "ESRI Shapefile", "KML"]
            output_format = st.selectbox("Select output vector format", options)
            if st.button("Convert Vector"):
                ext = output_format.split()[0].lower() if output_format != "ESRI Shapefile" else "shp"
                output_file = os.path.join(tmpdir, f"converted.{ext}")
                convert_vector(input_path, output_file, output_format)
                with open(output_file, "rb") as f:
                    st.download_button("Download converted vector file", f, file_name=f"converted.{ext}")

        elif is_raster(input_path):
            st.success("Raster data detected.")
            options = ["GTiff", "COG", "JPEG", "PNG"]
            output_format = st.selectbox("Select output raster format", options)
            if st.button("Convert Raster"):
                ext = output_format.lower()
                output_file = os.path.join(tmpdir, f"converted.{ext}")
                convert_raster(input_path, output_file, output_format)
                with open(output_file, "rb") as f:
                    st.download_button("Download converted raster file", f, file_name=f"converted.{ext}")

        elif is_point_cloud(input_path):
            st.success("Point cloud data detected.")
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
            options = ["ESRI Shapefile"]
            output_format = st.selectbox("Select output format", options)
            if st.button("Convert CSV to Shapefile"):
                shp_folder = os.path.join(tmpdir, "shp_output")
                os.makedirs(shp_folder, exist_ok=True)
                shp_path = csv_to_shp(input_path, shp_folder)
                zip_path = os.path.join(tmpdir, "shapefile.zip")
                zip_shapefile(shp_folder, zip_path)
                with open(zip_path, "rb") as f:
                    st.download_button("Download Shapefile ZIP", f, file_name="shapefile.zip")

        else:
            st.error("Unsupported or corrupted file.")
