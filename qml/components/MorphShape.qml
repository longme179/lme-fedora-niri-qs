// Role: MorphShape.qml (shared layer, fan-in 3).
// Shared component/helper; keep API stable for wide QML reuse.
import QtQuick
import "shapes"
import "shapes/Polygons.js" as Polygons
ShapeCanvas {
    property string shape: "circle"
    roundedPolygon: Polygons.shape(shape)
    fitToCanvas: true
}
