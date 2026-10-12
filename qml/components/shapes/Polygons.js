.pragma library
.import "shapes/rounded-polygon.js" as Polygon
.import "shapes/corner-rounding.js" as Corner
var cache = {};
function shape(name) {
    if (cache[name]) return cache[name];
    const count = name === "square" ? 4 : name === "flower" ? 12 : 16;
    const points=[];
    for (let i=0;i<count;i++) {
        const angle=2*Math.PI*i/count - Math.PI/4;
        const radius=name === "flower" && i%2 ? .72 : 1;
        points.push(Math.cos(angle)*radius,Math.sin(angle)*radius);
    }
    cache[name]=Polygon.RoundedPolygon.fromVertices(points,new Corner.CornerRounding(name === "square" ? .35 : .18)).normalized();
    return cache[name];
}
