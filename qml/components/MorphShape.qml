import QtQuick
import "shapes"
import "shapes/Polygons.js" as Polygons
ShapeCanvas {
    property string shape: "circle"
    roundedPolygon: Polygons.shape(shape)
    fitToCanvas: true
}
