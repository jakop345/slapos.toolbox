$(document).ready( function() {
  var send = false;
  $("#update").click(function(){
    var haspwd = false;
    var hasAccount = !($("input#hasAccount").val() === "");
    if($("input#username").val() === "" || !$("input#username").val().match(/^[\w\d\._-]+$/)){
  		$("#error").Popup("Invalid user name. Please check it!", {type:'alert', duration:3000});
			return false;
		}
    else if ($("input#username").val().length <6){
      $("#error").Popup("Username must have at least 6 characters", {type:'alert', duration:3000});
      return false;
    }
		if($("input#name").val() === ""){
			$("#error").Popup("Please enter your name and surname!", {type:'alert', duration:3000});
  		return false;
		}
		if(!$("input#email").val().match(/^([a-zA-Z0-9_\.\-])+\@(([a-zA-Z0-9\-])+\.)+([a-zA-Z0-9]{2,4})+$/)){
			$("#error").Popup("Please enter a valid email adress!", {type:'alert', duration:3000});
			return false;
		}
    if(!hasAccount && !$("input#password").val().match(/^[\w\d\._-]+$/)){
      $("#error").Popup("Please enter your new password!", {type:'alert', duration:3000});
      return false;
    }
    if ($("input#password").val() !== "" && $("input#password").val().length <6){
      $("#error").Popup("The password must have at least 6 characters", {type:'alert', duration:3000});
      return false;
    }
    if($("input#password").val() !== ""){
      if($("input#password").val() === "" || !$("input#password").val().match(/^[\w\d\._-]+$/)){
      	$("#error").Popup("Please enter your new password!", {type:'alert', duration:3000});
  			return false;
  		}
      if($("input#password").val() !== $("input#cpassword").val()){
        $("#error").Popup("your password does not match!", {type:'alert', duration:3000});
    		return false;
      }
      haspwd = true;
    }
    if(!$("input#rcode").val().match(/^[\w\d]+$/)){
    	$("#error").Popup("Please enter your password recovery code.", {type:'alert', duration:3000});
			return false;
		}
    if(send) return false;
    send = true;
    $.ajax({
  		type: "POST",
			url: $SCRIPT_ROOT + ((hasAccount)? '/updateAccount':'/configAccount'),
			data: {name: $("input#name").val(), username:$("input#username").val(), email:$("input#email").val(),
				password:((haspwd) ? $("input#password").val():""), rcode:$("input#rcode").val()},
			success: function(data){
        if(data.code ==1){
          location.href = $SCRIPT_ROOT+"/"
        }
        else{
          $("#error").Popup(data.result, {type:'error', duration:5000});
        }
        send = false;
			},
      error:function(){send = false;}
    });
    return false;
  });
});