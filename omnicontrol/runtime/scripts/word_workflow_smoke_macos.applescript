on run argv
    set outputDir to item 1 of argv
    set wordAppPath to item 2 of argv
    set outputDocx to outputDir & "/word-workflow.docx"
    set outputPdf to outputDir & "/word-workflow.pdf"
    set docRef to missing value

    try
        tell application "Microsoft Word"
            activate
            set docRef to create new document
            set content of text object of docRef to "OmniControl Word Workflow" & return & "Step 1: body write" & return & "Step 2: exported artifact at " & ((current date) as text)
            save as docRef file name outputDocx
            save as docRef file name outputPdf file format format PDF
            close docRef saving no
        end tell

        return "{\"status\":\"ok\",\"output_docx\":\"" & my escapeJson(outputDocx) & "\",\"output_pdf\":\"" & my escapeJson(outputPdf) & "\",\"word_path\":\"" & my escapeJson(wordAppPath) & "\"}"
    on error errMsg
        try
            tell application "Microsoft Word"
                if docRef is not missing value then
                    close docRef saving no
                end if
            end tell
        end try
        return "{\"status\":\"error\",\"error\":\"" & my escapeJson(errMsg) & "\",\"output_docx\":\"" & my escapeJson(outputDocx) & "\",\"output_pdf\":\"" & my escapeJson(outputPdf) & "\",\"word_path\":\"" & my escapeJson(wordAppPath) & "\"}"
    end try
end run

on escapeJson(textValue)
    set escapedText to textValue
    set escapedText to my replaceText("\\", "\\\\", escapedText)
    set escapedText to my replaceText("\"", "\\\"", escapedText)
    set escapedText to my replaceText(return, "\\n", escapedText)
    set escapedText to my replaceText(linefeed, "\\n", escapedText)
    return escapedText
end escapeJson

on replaceText(findText, replaceText, sourceText)
    set AppleScript's text item delimiters to findText
    set sourceItems to text items of sourceText
    set AppleScript's text item delimiters to replaceText
    set newText to sourceItems as text
    set AppleScript's text item delimiters to ""
    return newText
end replaceText
