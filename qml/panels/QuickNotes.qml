import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"
ColumnLayout {
    spacing: 10
    RowLayout {
        Layout.fillWidth: true
        LabelText { text: "Quick notes"; font.weight: Font.Bold; font.pixelSize: 18; Layout.fillWidth: true }
        LabelText { text: ShellState.demo ? "Preview only" : NotesState.conflict ? "Conflict" : NotesState.dirty ? "Unsaved" : "Saved"; color: NotesState.dirty || NotesState.conflict ? Theme.yellow : Theme.muted; font.pixelSize: 12 }
    }
    ScrollView {
        Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 280; clip: true
        TextArea {
            id: editor; objectName: "quickNotesEditor"; text: NotesState.content
            placeholderText: "Write a thought, a draft, or meeting notes…"; wrapMode: TextEdit.Wrap
            color: Theme.fieldText; selectionColor: Theme.accent; selectedTextColor: Theme.onPrimary
            font.family: Theme.fontFamily; font.pixelSize: Theme.bodySize; padding: 14
            background: Rectangle { color: Theme.fieldFill; radius: 16; border.color: editor.activeFocus ? Theme.accent : Theme.outlineVariant; border.width: 1 }
            Accessible.name: "Quick notes editor"
            onTextChanged: if(text!==NotesState.content) NotesState.edit(text)
            Connections { target: NotesState; function onContentChanged() { if(editor.text!==NotesState.content) { const cursor=editor.cursorPosition; editor.text=NotesState.content; editor.cursorPosition=Math.min(cursor,editor.length); } } }
        }
    }
    LabelText { visible: !!NotesState.error; text: NotesState.error; color: Theme.red; wrapMode: Text.Wrap; Layout.fillWidth: true }
    RowLayout {
        LabelText { text: NotesState.content.length+" characters · autosave"; color: Theme.muted; font.pixelSize: 12; Layout.fillWidth: true }
        LiquidButton { text: "Copy"; onClicked: ShellState.run("copyText",{text:NotesState.content}) }
        LiquidButton { text: NotesState.conflict ? "Reload disk version" : "Save"; onClicked: { if(NotesState.conflict) NotesState.reload(); else NotesState.save(); } }
    }
    Component.onDestruction: NotesState.save()
}
