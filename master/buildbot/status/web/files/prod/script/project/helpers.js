define(["jquery","screensize"],function(e,t){var n;return n={init:function(){e("#builders_page").length&&window.location.search!=""&&n.codeBaseBranchOverview(),e("#tb-root").length!=0&&n.updateBuilders(),n.menuItemWidth(t.isMediumScreen()),e(window).resize(function(){n.menuItemWidth(t.isMediumScreen())}),n.selectBuildsAction(),e(function(){var n=/chrome/.test(navigator.userAgent.toLowerCase()),r=navigator.platform.toUpperCase().indexOf("WIN")!==-1;n&&r&&e("body").addClass("chrome win")}),n.toolTip(".ellipsis-js"),n.parseReasonString(),n.runIndividualBuild(),n.setFullName(e("#buildForm .full-name-js, #authUserName")),e("#authUserBtn").click(function(e){n.eraseCookie("fullName","","eraseCookie")})},setFullName:function(e){var t=e.is("input")?"val":"text";e[t](n.getCookie("fullName"))},runIndividualBuild:function(){e(".run-build-js").click(function(t){e(".remove-js").remove(),t.preventDefault();var r=e(this).prev().attr("data-b"),i=e(this).prev().attr("data-indexb"),s='<div id="bowlG"><div id="bowl_ringG"><div class="ball_holderG"><div class="ballG"></div></div></div></div>';e("body").append(s).show(),e.get("",{rt_update:"extforms",datab:r,dataindexb:i}).done(function(t){e("#bowlG").remove();var r=e("<div/>").attr("id","formCont").append(e(t)).appendTo("body").hide();n.setFullName(e("#usernameDisabled, #usernameHidden",r)),e(".command_forcebuild",r).submit()})})},parseReasonString:function(){e(".codebases-list .reason-txt").each(function(){var t=e(this).text().trim();t==="A build was forced by '':"&&e(this).remove()})},selectBuildsAction:function(){e("#selectall").click(function(){e(".fi-js").prop("checked",this.checked)}),e("#submitBtn").click(function(){e("#formWrapper form").submit()}),e(".force-individual-js").click(function(t){t.preventDefault();var n=e(this).prev().prev().val(),r=e('<input checked="checked" name="cancelselected" type="hidden" value="'+n+'"  />');e(r).insertAfter(e(this)),e("#formWrapper form").submit()})},updateBuilders:function(){e.ajax({url:"/json?filter=0",dataType:"json",type:"GET",cache:!1,success:function(t){function s(t){var n=0;return e.each(t,function(){n+=parseFloat(this)||0}),n}var n=[],r=[],i=[];e.each(t.builders,function(e,t){n.push(e),r.push(t.pendingBuilds),t.state=="building"&&i.push(t.currentBuilds)});var o=[];e.each(t.slaves,function(e){o.push(e)});var u=[];e.each(t.project,function(e){u.push(e)}),e("#slavesNr").text(o.length),e("#pendingBuilds").text(s(r))}})},codeBaseBranchOverview:function(){var t=decodeURIComponent(window.location.search),n=t.split("&"),r=e('<div class="border-table-holder"><table class="codebase-branch-table"><tr class="codebase"><th>Codebase</th></tr><tr class="branch"><th>Branch</th></tr></table></div>');e(r).appendTo(e(".filter-table-input")),e(n).each(function(t){var n=this.split("=");if(n[0].indexOf("_branch")>0){var r=this.split("_branch")[0];t==0&&(r=this.replace("?","").split("_branch")[0]);var i=this.split("=")[1];e("tr.codebase").append("<td>"+r+"</td>"),e("tr.branch").append("<td>"+i+"</td>")}})},menuItemWidth:function(t){if(t){var n=0;e(".breadcrumbs-nav li").each(function(){n+=e(this).outerWidth()}),e(".breadcrumbs-nav").width(n+100)}else e(".breadcrumbs-nav").width("")},toolTip:function(t){e(t).parent().hover(function(){var n=e(t,this).attr("data-txt"),r=e("<div/>").addClass("tool-tip").text(n);e(this).append(e(r).css({top:e(t,this).position().top-10,left:e(t,this).position().left-20}).show())},function(){e(".tool-tip").remove()}),e(document).bind("click touchstart",function(t){e(".tool-tip").remove(),e(this).unbind(t)})},summaryArtifactTests:function(){var t=e("li.artifact-js").clone(),n=e("#showArtifactsJS");t.length>0?n.removeClass("no-artifacts").addClass("more-info mod-1 popup-btn-js-2").text("("+t.length+") Artifacts ").next().find(".builders-list").append(t):n.text("No Artifacts");var r=e(".s-logs-js").clone(),i=e("#testsListJS"),s=[];e(r).each(function(){var t=e(this).text().split(".").pop();(t==="xml"||t==="html")&&s.push(e(this))}),s.length>0&&(i.append(e("<li>Test Results</li>")),i.append(s))},setCookie:function(e,t,n){var r=new Date,i=new Date(r.getTime()+2592e6);if(n===undefined)var s=i.toGMTString();else var s="Thu, 01 Jan 1970 00:00:00 GMT;";document.cookie=e+"="+escape(t)+"; path=/; expires="+s},getCookie:function(e){var t=new RegExp(e+"=([^;]+)"),n=t.exec(document.cookie);return n!=null?unescape(n[1]):""},eraseCookie:function(e,t,r){n.setCookie(e,t,r)}},n});