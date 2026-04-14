on run argv
    set targetUrl to "data:text/html,<title>OmniControl Safari Write</title><textarea id='omni'></textarea>"
    if (count of argv) > 0 then
        set targetUrl to item 1 of argv
    end if

    try
        tell application "Safari"
            activate
            if not (exists document 1) then
                make new document
            end if
            set URL of front document to targetUrl
        end tell

        my waitForDocument()

        tell application "Safari"
            set payload to do JavaScript "const area = document.getElementById('omni') || (() => { const t = document.createElement('textarea'); t.id = 'omni'; document.body.appendChild(t); return t; })(); document.title = 'OmniControl Safari Write'; area.value = 'OmniControl wrote this'; window.__omniMarker = 'written'; JSON.stringify({status: 'ok', title: document.title, href: location.href, marker: window.__omniMarker, textarea_value: area.value, readyState: document.readyState});" in front document
        end tell
        return payload
    on error errMsg
        return "{\"status\":\"error\",\"error\":\"" & my escapeJson(errMsg) & "\"}"
    end try
end run

on waitForDocument()
    repeat 40 times
        delay 0.25
        try
            tell application "Safari"
                set readyState to do JavaScript "document.readyState" in front document
            end tell
            if readyState is "complete" or readyState is "interactive" then
                exit repeat
            end if
        end try
    end repeat
end waitForDocument

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
