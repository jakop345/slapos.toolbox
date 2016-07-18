/*jslint undef: true */
/*global $, document, window, $SCRIPT_ROOT */
/* vim: set et sts=4: */

$(document).ready(function () {
    "use strict";
    var send = false;
    $("#information").Tooltip();

    $("#update").click(function () {
        var haspwd = false;
        if ($("select#username").val() === "" || !$("select#username").val().match(/^[\w\d\._\-]+$/)) {
            $("#error").Popup("Invalid user name. Please check it!", {type: 'alert', duration: 3000});
            return false;
        }
        if ($("input#name").val() === "") {
            $("#error").Popup("Please enter your full name for git configuration!", {type: 'alert', duration: 3000});
            return false;
        }
        if (!$("input#email").val().match(/^([a-zA-Z0-9_\.\-])+\@(([a-zA-Z0-9\-])+\.)+([a-zA-Z0-9]{2,4})+$/)) {
            $("#error").Popup("Please enter a valid email address!", {type: 'alert', duration: 3000});
            return false;
        }
        if ($("input#password").val() !== "") {
            if ($("input#password").val() === "" || !$("input#password").val()) {
                $("#error").Popup("Please enter your current password!", {type: 'alert', duration: 3000});
                return false;
            }
            if ($("input#npassword").val() === "" || !$("input#npassword").val()) {
                $("#error").Popup("Please enter your new password!", {type: 'alert', duration: 3000});
                return false;
            }
            if ($("input#npassword").val() !== $("input#cpassword").val()) {
                $("#error").Popup("your new password does not match!", {type: 'alert', duration: 3000});
                return false;
            }
            haspwd = true;
        }
        if (send) {
            return false;
        }
        send = true;
        $.ajax({
            type: "POST",
            url: $SCRIPT_ROOT + '/updateAccount',
            data: {
                name: $("input#name").val(),
                username: $("select#username").val(),
                email: $("input#email").val(),
                password: ((haspwd) ? $("input#password").val() : ""),
                new_password: ((haspwd) ? $("input#npassword").val() : "")
            },
            success: function (data) {
                if (data.code === 1) {
                    if ($("input#npassword").val() !== "") {
                        var url = 'https://' + $("select#username").val() + ':' + $("input#npassword").val() + '@' + location.host + $SCRIPT_ROOT + '/';
                        window.location.href = url;
                    } else {
                      $("#error").Popup("Account information saved successfully!", {type: 'info', duration: 5000});
                    }
                } else {
                    $("#error").Popup(data.result, {type: 'error', duration: 5000});
                }
                send = false;
            },
            error: function () { send = false; }
        });
        return false;
    });
    $("#save").click(function () {
        if (send) {
            return false;
        }
        send = true;
        $.ajax({
            type: "POST",
            url: $SCRIPT_ROOT + '/updateBuildAndRunConfig',
            data: {
                run_instance: $("input#run_instance").is(':checked'),
                run_software: $("input#run_software").is(':checked'),
                max_run_instance: $("input#max_run_instance").val(),
                max_run_software: $("input#max_run_software").val()
            },
            success: function (data) {
                if (data.code === 1) {
                    $("#error").Popup(data.result, {type: 'alert', duration: 5000});
                } else {
                    $("#error").Popup(data.result, {type: 'error', duration: 5000});
                }
                send = false;
            },
            error: function () { send = false; }
        });
        return false;
    });
    $("#add_user").click(function () {
        if ($("input#new_username").val() === "" || !$("input#new_username").val().match(/^[\w\d\._\-]+$/)) {
            $("#error").Popup("Invalid user name. Please check it!", {type: 'alert', duration: 3000});
            return false;
        }
        if (send) {
            return false;
        }
        send = true;
        $.ajax({
            type: "POST",
            url: $SCRIPT_ROOT + '/addUser',
            data: {
                username: $("input#new_username").val(),
                password: $("input#new_password").val()
            },
            success: function (data) {
                if (data.code === 1) {
                    $("#error").Popup(data.result, {type: 'info', duration: 5000});
                } else if (data.code === 0) {
                    $("#error").Popup(data.result, {type: 'error', duration: 5000});
                } else {
                    $("#error").Popup(data.result, {type: 'alert', duration: 5000});
                }
                send = false;
                $("input#new_username").val('');
                $("input#new_password").val('');
            },
            error: function () { send = false; }
        });
        return false;
    });
});
