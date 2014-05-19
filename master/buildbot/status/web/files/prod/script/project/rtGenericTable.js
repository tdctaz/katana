define(["jquery","dataTables","timeElements","text!hbCells","extend-moment","handlebars","helpers","moment"],function(e,t,n,r,i,s,o,u){var a=Handlebars.compile(r),f={getPropertyOnData:function(e,t){return t===undefined?undefined:typeof t=="string"||t instanceof String?e[t]:t(e)},buildPropertiesContainsRevision:function(t){var n=!0;return e.each(t,function(e,t){return t.length>0&&t[0]==="revision"&&t[1].length!==0?(n=!1,!1):!0}),n}},l={revision:function(e,t){return{aTargets:[e],sClass:"txt-align-left",mRender:function(e,n,r){var i=f.getPropertyOnData(r,t),s=!1;return r.properties!==undefined&&(s=!f.buildPropertiesContainsRevision(r.properties)),a({revisionCell:!0,sourceStamps:i,history_build:s})}}},buildID:function(e){return{aTargets:[e],sClass:"txt-align-left",mRender:function(e,t,n){return a({buildID:!0,data:n})}}},buildStatus:function(t,n){return{aTargets:[t],sClass:n===undefined?"txt-align-left":n,mRender:function(e,t,n){return a({buildStatus:!0,build:n})},fnCreatedCell:function(t,n,r){e(t).removeClass().addClass(r.results_text)}}},shortTime:function(e,t){return{aTargets:[e],sClass:"txt-align-left",mRender:function(e,n,r){var s=f.getPropertyOnData(r,t);return i.getDateFormatted(s)}}},slaveName:function(e,t,n,r){return{aTargets:[e],sClass:r===undefined?"txt-align-left":r,mRender:function(e,r,i){var s=f.getPropertyOnData(i,t),o=f.getPropertyOnData(i,n);return a({slaveName:!0,name:s,url:o})}}},slaveStatus:function(t){return{aTargets:[t],mRender:function(e,t,n){var r,i=!1;return n.connected===undefined||n.connected===!1?r="Offline":n.connected===!0&&n.runningBuilds===undefined?r="Idle":n.connected===!0&&n.runningBuilds.length>0&&(r=n.runningBuilds.length+" build(s) ",i=!0),a({slaveStatus:!0,showStatusTxt:r,showSpinIcon:i})},fnCreatedCell:function(t,n,r){if(r.connected===undefined)e(t).addClass("offline");else if(r.connected===!0&&r.runningBuilds===undefined)e(t).addClass("idle");else if(r.connected===!0&&r.runningBuilds.length>0){var i=0;r.runningBuilds!==undefined&&(e.each(r.runningBuilds,function(e,t){t.eta!==undefined&&t.eta<0&&(i+=1)}),i=i>0?i:!1),e(t).addClass("building").find("a.popup-btn-json-js").data({showRunningBuilds:r}),i&&(e(t).removeClass("building").addClass("overtime tooltip").attr("title","One or more builds on overtime"),o.tooltip(e(t)))}}}},buildProgress:function(t,r){return{aTargets:[t],sClass:"txt-align-left",mRender:function(e,t,n){return a({buildProgress:!0,showPending:!r,pendingBuilds:r?undefined:n.pendingBuilds,currentBuilds:r?[n]:n.currentBuilds,builderName:n.name})},fnCreatedCell:function(t,r,i){var s=e(t).find(".percent-outer-js");e.each(s,function(t,r){var i=e(r);n.addProgressBarElem(i,i.attr("data-starttime"),i.attr("data-etatime"))})}}},buildLength:function(e){return{aTargets:[e],sClass:"txt-align-left",mRender:function(e,t,n){var r=n.times;if(r!==undefined){var i=u.duration((r[1]-r[0])*1e3);return r.length===3&&(i=u.duration((r[2]-r[0])*1e3)),"{0}m {1}s ".format(i.minutes(),i.seconds())}return"N/A"}}}},c={buildTableInit:function(n){var r={};return r.aoColumns=[{mData:null,sTitle:"#",sWidth:"5%"},{mData:null,sTitle:"Date",sWidth:"10%"},{mData:null,sTitle:"Revision",sWidth:"30%"},{mData:null,sTitle:"Result",sWidth:"32%",sClass:""},{mData:null,sTitle:"Build Time",sWidth:"10%"},{mData:null,sTitle:"Slave",sWidth:"13%"}],r.fnRowCallback=function(t,n){n.properties!==undefined&&!f.buildPropertiesContainsRevision(n.properties)&&e(t).addClass("italic")},r.aoColumnDefs=[l.buildID(0),l.shortTime(1,function(e){return e.times[0]}),l.revision(2,"sourceStamps"),l.buildStatus(3),l.buildLength(4),l.slaveName(5,function(e){return e.slave_friendly_name!==undefined?e.slave_friendly_name:e.slave},"slave_url","txt-align-right")],t.initTable(n,r)},rtfGenericTableProcess:function(e,t){n.clearTimeObjects(e),e.fnClearTable();try{e.fnAddData(t),n.updateTimeObjects()}catch(r){}}};return{table:c,cell:l}});