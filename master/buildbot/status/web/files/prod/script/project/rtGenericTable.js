define(["jquery","dataTables","timeElements","text!hbCells","extend-moment","handlebars","helpers"],function(e,t,n,r,i,s){var o=Handlebars.compile(r),u={getPropertyOnData:function(e,t){return t===undefined?undefined:typeof t=="string"||t instanceof String?e[t]:t(e)}},a={revision:function(e){return{aTargets:[e],sClass:"txt-align-left",mRender:function(e,t,n){return o({revisionCell:!0,data:n})}}},buildID:function(e){return{aTargets:[e],sClass:"txt-align-left",mRender:function(e,t,n){return o({buildID:!0,data:n})}}},buildStatus:function(t,n){return{aTargets:[t],sClass:n===undefined?"txt-align-left":n,mRender:function(e,t,n){return o({buildStatus:!0,build:n})},fnCreatedCell:function(t,n,r){e(t).removeClass().addClass(r.results_text)}}},shortTime:function(e,t){return{aTargets:[e],sClass:"txt-align-left",mRender:function(e,n,r){var s=u.getPropertyOnData(r,t);return i.getDateFormatted(s)}}},slaveName:function(e,t,n,r){return console.log(),{aTargets:[e],sClass:r===undefined?"txt-align-left":r,mRender:function(e,r,i){var s=u.getPropertyOnData(i,t),a=u.getPropertyOnData(i,n);return o({slaveName:!0,name:s,url:a})}}},slaveStatus:function(t){return{aTargets:[t],mRender:function(e,t,n){var r,i=!1;return n.connected===undefined||n.connected===!1?r="Offline":n.connected===!0&&n.runningBuilds===undefined?r="Idle":n.connected===!0&&n.runningBuilds.length>0&&(r=n.runningBuilds.length+" build(s) ",i=!0),o({slaveStatus:!0,showStatusTxt:r,showSpinIcon:i})},fnCreatedCell:function(t,n,r){if(r.connected===undefined)e(t).addClass("offline");else if(r.connected===!0&&r.runningBuilds===undefined)e(t).addClass("idle");else if(r.connected===!0&&r.runningBuilds.length>0){var i=0;r.runningBuilds!==undefined&&(e.each(r.runningBuilds,function(e,t){t.eta!==undefined&&t.eta<0&&(i+=1)}),i=i>0?i:!1),e(t).addClass("building").find("a.popup-btn-json-js").data({showRunningBuilds:r}),i&&(e(t).removeClass("building").addClass("overtime tooltip").attr("title","One or more builds on overtime"),s.tooltip(e(t)))}}}},buildProgress:function(t,r){return{aTargets:[t],sClass:"txt-align-left",mRender:function(e,t,n){return o({buildProgress:!0,showPending:!r,pendingBuilds:r?undefined:n.pendingBuilds,currentBuilds:r?[n]:n.currentBuilds,builderName:n.name})},fnCreatedCell:function(t,r,i){var s=e(t).find(".percent-outer-js");e.each(s,function(t,r){var i=e(r);n.addProgressBarElem(i,i.attr("data-starttime"),i.attr("data-etatime"))})}}}},f={buildTableInit:function(e){var n={};return n.aoColumns=[{mData:null,sTitle:"#",sWidth:"5%"},{mData:null,sTitle:"Date",sWidth:"20%"},{mData:null,sTitle:"Revision",sWidth:"30%"},{mData:null,sTitle:"Result",sWidth:"35%",sClass:""},{mData:null,sTitle:"Slave",sWidth:"10%"}],n.aoColumnDefs=[a.buildID(0),a.shortTime(1,function(e){return e.times[0]}),a.revision(2),a.buildStatus(3),a.slaveName(4,"slave_friendly_name","slaveName","txt-align-right")],t.initTable(e,n)},rtfGenericTableProcess:function(e,t){n.clearTimeObjects(e),e.fnClearTable();try{e.fnAddData(t),n.updateTimeObjects()}catch(r){}}};return{table:f,cell:a}});