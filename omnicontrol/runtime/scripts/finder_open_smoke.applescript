on run argv
    set targetPath to ""
    if (count of argv) > 0 then
        set targetPath to item 1 of argv
    end if

    try
        tell application "Finder"
            activate
            if targetPath is not "" then
                set targetAlias to POSIX file targetPath as alias
                reveal targetAlias
                set resolvedPath to POSIX path of targetAlias
            else
                open home
                set resolvedPath to POSIX path of (home as alias)
            end if
            delay 0.5
            set windowName to name of front window
        end tell

        tell application "System Events"
            set finderRunning to exists process "Finder"
        end tell

        return "{\"status\":\"ok\",\"resolved_path\":\"" & my escapeJson(resolvedPath) & "\",\"window_name\":\"" & my escapeJson(windowName) & "\",\"finder_running\":" & my boolJson(finderRunning) & "}"
    on error errMsg
        return "{\"status\":\"error\",\"error\":\"" & my escapeJson(errMsg) & "\"}"
    end try
end run

on boolJson(flagValue)
    if flagValue then
        return "true"
    end if
    return "false"
end boolJson

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
