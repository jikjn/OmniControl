on run argv
    set sourceDocx to item 1 of argv
    set outputPdf to item 2 of argv
    set wordAppPath to item 3 of argv
    set docRef to missing value

    try
        tell application "Microsoft Word"
            activate
            open (POSIX file sourceDocx)
            delay 0.5
            set docRef to active document
            save as docRef file name outputPdf file format format PDF
            close docRef saving no
        end tell

        return "{\"status\":\"ok\",\"source\":\"" & my escapeJson(sourceDocx) & "\",\"output\":\"" & my escapeJson(outputPdf) & "\",\"word_path\":\"" & my escapeJson(wordAppPath) & "\"}"
    on error errMsg
        try
            tell application "Microsoft Word"
                if docRef is not missing value then
                    close docRef saving no
                end if
            end tell
        end try
        return "{\"status\":\"error\",\"error\":\"" & my escapeJson(errMsg) & "\",\"source\":\"" & my escapeJson(sourceDocx) & "\",\"output\":\"" & my escapeJson(outputPdf) & "\",\"word_path\":\"" & my escapeJson(wordAppPath) & "\"}"
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
