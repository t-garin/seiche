"""
Interpolates the data on 1D cross sections along the centerline.

Uses a given river centerline and some hydraulic gauges stations.
"""

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import shapely


# ---
def curvplot(
    centerline: shapely.LineString, multipoint: shapely.MultiPoint
) -> None:
    """
    Plot a river centerline and a set of points (with z values) using geopandas and matplotlib.

    Parameters
    ----------
    centerline : shapely.LineString
        The river centerline geometry.

    multipoint : shapely.MultiPoint
        Points with z values to plot along the centerline.

    Returns
    -------
    None

    """
    gdfplot = gpd.GeoDataFrame(
        data=[point.z for point in multipoint.geoms],
        geometry=[point for point in multipoint.geoms],
        columns=["z"],
    )
    ax = gdfplot.plot("z", legend=True, legend_kwds={"shrink": 0.5})
    gpd.GeoSeries(centerline).plot(ax=ax)
    plt.show()


# ---
def curvinterp_linspace(
    centerline: shapely.LineString,
    ptinf: shapely.Point,
    ptsup: shapely.Point,
    n_interp: int = 1,
    infval: float | None = None,
    supval: float | None = None,
) -> shapely.MultiPoint:
    """
    Interpolate n points along a centerline between two points, with optional z value interpolation.

    Parameters
    ----------
    centerline : shapely.LineString
        The river centerline geometry.

    ptinf : shapely.Point
        Start point for interpolation.

    ptsup : shapely.Point
        End point for interpolation.

    n_interp : int, default: 1
        Number of points to interpolate between ptinf and ptsup.

    infval : float, default: None
        Z value for ptinf if centerline has no z.

    supval : float, default: None
        Z value for ptsup if centerline has no z.


    Returns
    -------
    shapely.MultiPoint
        Interpolated points along the centerline, with z if available.

    """
    assert n_interp >= 0, "n_interp must be >= 0"
    # curvilinear abcissa for ptinf and ptsup, projects points onto the centerline, even if outside the geometry
    curvabs_inf = centerline.project(ptinf, normalized=True)
    curvabs_sup = centerline.project(ptsup, normalized=True)
    # linspace used  to generate interpolation points
    linspace = np.linspace(curvabs_inf, curvabs_sup, n_interp + 2)
    points = centerline.interpolate(linspace, normalized=True).tolist()
    return curvinterp(
        centerline=centerline, points=points, infval=infval, supval=supval
    )


# ---
def curvinterp(
    centerline: shapely.LineString,
    points: list[shapely.Point] | None = None,
    infval: float | None = None,
    supval: float | None = None,
) -> shapely.LineString:
    """
    Interpolate z values along a centerline at given points, using z from centerline or linear interpolation.

    Parameters
    ----------
    centerline : shapely.LineString
        The river centerline geometry.

    points : list[shapely.Point], default: None
        Points to interpolate z values at.

    infval : float, default: None
        Z value for first point if centerline has no z.

    supval : float, default: None
        Z value for last point if centerline has no z.

    Returns
    -------
    shapely.LineString | shapely.MultiPoint
        Geometry with interpolated z values.

    """
    # generating curvilinear abcissa of the points by projecting them on the centerline
    curvabs = [centerline.project(point, normalized=True) for point in points]
    # generating points using shapely.LineString.interpolate
    multipoint = shapely.MultiPoint(
        centerline.interpolate(curvabs, normalized=True)
    )
    # if the points in centerline are 2D, we interpolate linearly the values based on infval and supval
    if not centerline.has_z:
        assert (infval is not None) and (supval is not None), (
            "Please specify a value for 'infval' and 'supval'"
        )
        assert len(points) >= 2, (
            "points list must be at least of length 2 if using linear interpolation"
        )
        values = np.interp(
            curvabs, xp=[curvabs[0], curvabs[-1]], fp=[infval, supval]
        )
        multipoint = shapely.MultiPoint(
            [
                (point.x, point.y, z)
                for point, z in zip(multipoint.geoms, values, strict=True)
                if z is not None
            ]
        )
    return multipoint


# ---
def modify_z(line: shapely.LineString, func=lambda x: x) -> shapely.LineString:
    """
    Modify the z coordinates of a LineString by applying a function to each z value.

    Parameters
    ----------
    line : shapely.LineString
        Input LineString with z coordinates.

    func : callable
        Function to apply to each z value.

    Returns
    -------
    shapely.LineString
        LineString with modified z coordinates.

    """
    # modifies the z coordinates of a shapely linestring by applying a function 'func'
    assert line.has_z, "Line does not have z coordinates"
    return shapely.LineString(
        [[point[0], point[1], func(point[2])] for point in line.coords]
    )


# ---
def remove_z(line: shapely.LineString) -> shapely.LineString:
    """
    Remove the z coordinates from a LineString, returning a 2D LineString.

    Parameters
    ----------
    line : shapely.LineString
        Input shapely.LineString with or without z coordinates.

    Returns
    -------
    shapely.LineString
        2D LineString without z coordinates.

    """
    # removes the z coords in the points of the input linestring
    return shapely.LineString(shapely.get_coordinates(line, include_z=False))


# ---
if __name__ == "__main__":
    # pass
    # read BDTopage
    centerlines = gpd.read_file(
        "/Users/garin/Downloads/BD_Topage_FXX_2019/TronconHydrographique_FXX-shp/TronconHydrographique_FXX.shp",
        rows=10,
    )
    # extract a random centerline's shapely LineString
    centerline = centerlines.iloc[9].geometry

    # picking two random points
    ptinf = shapely.Point(530167.325, 6570690.753)
    ptsup = shapely.Point(529960.879, 6570614.042)
    pt = shapely.Point(
        (530167.325 + 529960.879) / 2, (6570690.753 + 6570614.042) / 2
    )

    # centerline = remove_z(centerline)
    # res2 = curvinterp(centerline, points = [ptinf, pt, ptsup], infval = 200, supval = 50)
    # curvplot(centerline, res)

    # with centerline z information
    res = curvinterp(centerline, points=[ptinf, pt, ptsup])
    curvplot(centerline, res)
    print(res)
    # without centerline z information
    centerline2 = remove_z(centerline)
    res2 = curvinterp(
        centerline2, points=[ptinf, pt, ptsup], infval=158.741, supval=153.386
    )
    curvplot(centerline2, res2)
    print(res2)
    # print(centerline)
    res3 = curvinterp_linspace(centerline, ptinf, ptsup, n_interp=3)
    curvplot(centerline, res3)
    print(res3)

    # def az(inp):
    #     if inp == 159:
    #         return 0
    #     else:
    #         return inp

    # res = modify_z(centerline, func = az)

    # print(res)
    # # with centerline z information
    # gdf = curvinterp2(centerline = centerline,
    #                  ptinf = ptinf, ptsup = ptsup, n_interp = 10)

    # print(gdf.head(10))
    # # gdf.value.plot()
    # # print(gdf)

    # # without centerline z information
    # centerline2 = remove_z(centerline)
    # gdf2 = curvinterp2(centerline = centerline2,
    #                 ptinf = ptinf, ptsup = ptsup,
    #                 infval = 158.741, supval = 153.386, n_interp = 10)

    # print(gdf2.head(10))

    # to do
    # change output to shapely multi point
    # allow to input fixed points instead of only linspace
    # function to modify centerline z information before curvinterp (add DEM...)
    # sortir 1D mascaret pour remettre dans cephee (PreCourlis) -> toolbox swot charlotte
    # dev cassan branche git
