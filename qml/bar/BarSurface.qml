import "../components"
import "../theme"

GlassPanel {
    objectName: "barSurface"
    role: "barFill"
    radius: height / 2
    topLeftRadius: Theme.barCornerRadius("topLeft", height)
    topRightRadius: Theme.barCornerRadius("topRight", height)
    bottomLeftRadius: Theme.barCornerRadius("bottomLeft", height)
    bottomRightRadius: Theme.barCornerRadius("bottomRight", height)
    border.width: Theme.barBorderWidth
    border.color: Theme.barBorder
}
