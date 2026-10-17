// SPDX-License-Identifier: GPL-3.0-only
// Caelestia-inspired soft-union geometry; see shaders/connected-popup.frag and THIRD_PARTY.md.
pragma ComponentBehavior: Bound
import QtQuick
import "../theme"

Item {
    id: root
    required property rect originRect
    required property rect popupRect
    property real progress: 0
    property real popupRadius: Theme.radius
    property color fill: Theme.alpha(Theme.panelFill,Theme.panelOpacity)
    readonly property real p: Math.max(0,Math.min(1,progress))
    // A distant popup detaches instead of leaving a thin cord across the desktop.
    readonly property real gap: Math.hypot(Math.max(0,Math.abs(cx-ox)-cw/2-originRect.width/2),Math.max(0,Math.abs(cy-oy)-ch/2-originRect.height/2))
    readonly property real connection: Math.max(0,Math.sin(Math.PI*Math.min(1,p/.65)))*Math.max(0,1-gap/100)
    readonly property real sourceScale: Math.min(1,connection*2)
    readonly property real neck: Math.min(24,originRect.height*.45)*connection
    readonly property real ox: originRect.x+originRect.width/2
    readonly property real oy: originRect.y+originRect.height/2
    readonly property real cx: ox+(popupRect.x+popupRect.width/2-ox)*p
    readonly property real cy: oy+(popupRect.y+popupRect.height/2-oy)*p
    readonly property real cw: originRect.width+(popupRect.width-originRect.width)*p
    readonly property real ch: originRect.height+(popupRect.height-originRect.height)*p
    readonly property rect bounds: Qt.rect(Math.min(originRect.x,cx-cw/2)-40,Math.min(originRect.y,cy-ch/2)-40,
        Math.max(originRect.x+originRect.width,cx+cw/2)-Math.min(originRect.x,cx-cw/2)+80,
        Math.max(originRect.y+originRect.height,cy+ch/2)-Math.min(originRect.y,cy-ch/2)+80)
    readonly property bool software: GraphicsInfo.api===GraphicsInfo.Software
    ShaderEffect {
        x:root.bounds.x;y:root.bounds.y;width:root.bounds.width;height:root.bounds.height;visible:!root.software
        readonly property vector2d viewport: Qt.vector2d(width,height)
        readonly property vector4d origin: Qt.vector4d(root.ox-x,root.oy-y,root.originRect.width/2*root.sourceScale,root.originRect.height/2*root.sourceScale)
        readonly property vector4d popup: Qt.vector4d(root.cx-x,root.cy-y,root.cw/2,root.ch/2)
        readonly property vector4d fillColor: Qt.vector4d(root.fill.r,root.fill.g,root.fill.b,root.fill.a)
        readonly property vector4d borderColor: Qt.vector4d(Theme.outlineVariant.r,Theme.outlineVariant.g,Theme.outlineVariant.b,Theme.outlineVariant.a)
        readonly property real popupRadius: root.popupRadius
        readonly property real neckRadius: root.neck
        readonly property real smoothing: Math.max(1,root.neck*.7)
        fragmentShader: Qt.resolvedUrl("shaders/connected-popup.frag.qsb")
    }
    Canvas {
        id: fallback
        x:root.bounds.x;y:root.bounds.y;width:root.bounds.width;height:root.bounds.height;visible:root.software
        function rounded(c,x,y,w,h,r) {
            r=Math.min(r,w/2,h/2);c.moveTo(x+r,y);c.lineTo(x+w-r,y);c.quadraticCurveTo(x+w,y,x+w,y+r);
            c.lineTo(x+w,y+h-r);c.quadraticCurveTo(x+w,y+h,x+w-r,y+h);c.lineTo(x+r,y+h);
            c.quadraticCurveTo(x,y+h,x,y+h-r);c.lineTo(x,y+r);c.quadraticCurveTo(x,y,x+r,y);c.closePath();
        }
        onWidthChanged: if (root.software) requestPaint()
        onHeightChanged: if (root.software) requestPaint()
        onPaint: {
            const c=getContext("2d");c.reset();c.clearRect(0,0,width,height);c.beginPath();
            rounded(c,root.cx-root.cw/2-x,root.cy-root.ch/2-y,root.cw,root.ch,root.popupRadius);
            if(root.neck>.1) {
                rounded(c,root.ox-root.originRect.width/2*root.sourceScale-x,root.oy-root.originRect.height/2*root.sourceScale-y,root.originRect.width*root.sourceScale,root.originRect.height*root.sourceScale,root.originRect.height/2*root.sourceScale);
                const dx=root.cx-root.ox,dy=root.cy-root.oy,len=Math.max(1,Math.hypot(dx,dy));
                const nx=-dy/len*root.neck,ny=dx/len*root.neck;
                c.moveTo(root.ox-x+nx,root.oy-y+ny);c.lineTo(root.cx-x+nx,root.cy-y+ny);
                c.lineTo(root.cx-x-nx,root.cy-y-ny);c.lineTo(root.ox-x-nx,root.oy-y-ny);c.closePath();
            }
            c.fillStyle=root.fill;c.fill();
        }
        Connections { target:root;function onProgressChanged(){if(root.software)fallback.requestPaint();}function onPopupRectChanged(){if(root.software)fallback.requestPaint();}function onOriginRectChanged(){if(root.software)fallback.requestPaint();}function onFillChanged(){if(root.software)fallback.requestPaint();} }
    }
}
