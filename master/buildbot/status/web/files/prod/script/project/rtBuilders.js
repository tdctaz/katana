define(["jquery","realtimePages","helpers","dataTables","mustache","libs/jquery.form","text!templates/builders.mustache","timeElements","rtGenericTable","popup"],function(t,e,l,a,i,s,n,r,u,d){var o,m;return o={init:function(){m=o.dataTableInit(t(".builders-table"));var a=e.defaultRealtimeFunctions();a.builders=o.realtimeFunctionsProcessBuilders,e.initRealtime(a);var i=t(".dataTables_wrapper .top");""!==window.location.search&&l.codeBaseBranchOverview(i)},realtimeFunctionsProcessBuilders:function(t){u.table.rtfGenericTableProcess(m,t.builders)},dataTableInit:function(e){var s={};return s.aoColumns=[{mData:null,sWidth:"20%"},{mData:null,sWidth:"15%"},{mData:null,sWidth:"10%"},{mData:null,sWidth:"15%",sType:"builder-status"},{mData:null,sWidth:"5%",bSortable:!1},{mData:null,sWidth:"15%",bSortable:!1},{mData:null,sWidth:"10%",sType:"natural"},{mData:null,sWidth:"10%",bSortable:!1}],s.aoColumnDefs=[{aTargets:[0],sClass:"txt-align-left",mRender:function(t,e,l){return i.render(n,{name:l.name,friendly_name:l.friendly_name,url:l.url})}},u.cell.buildProgress(1,!1),{aTargets:[2],sClass:"txt-align-left last-build-js",mRender:function(t,e,l){return i.render(n,{showLatestBuild:!0,latestBuild:l.latestBuild})},fnCreatedCell:function(e,a,i){if(void 0!==i.latestBuild){r.addTimeAgoElem(t(e).find(".last-run"),i.latestBuild.times[1]);var s=l.getTime(i.latestBuild.times[0],i.latestBuild.times[1]).trim();t(e).find(".small-txt").html("("+s+")"),t(e).find(".hidden-date-js").html(i.latestBuild.times[1])}}},{aTargets:[3],sClass:"txt-align-left",mRender:function(t,e,l){return"sort"===e?l:i.render(n,{showStatus:!0,latestBuild:l.latestBuild,data:l})},fnCreatedCell:function(e,l,a){var i=void 0===a.latestBuild?"":a.latestBuild;t(e).removeClass().addClass(i.results_text)}},{aTargets:[4],sClass:"txt-align-left",mRender:function(t,e,l){return i.render(n,{showShortcuts:!0,data:l})},fnCreatedCell:function(e,l,a){void 0!==a.latestBuild&&void 0!==a.latestBuild.artifacts&&d.initArtifacts(a.latestBuild.artifacts,t(e).find(".artifact-js"))}},u.cell.revision(5,function(t){return void 0!==t.latestBuild?t.latestBuild.sourceStamps:void 0},l.urlHasCodebases()),u.cell.buildLength(6,function(t){return void 0!==t.latestBuild?t.latestBuild.times:void 0}),{aTargets:[7],sClass:"txt-align-left",mRender:function(t,e,l){return i.render(n,{customBuild:!0,url:l.url,builderName:l.name})},fnCreatedCell:function(e){var l=t(e);d.initRunBuild(l.find(".custom-build"),l.find(".instant-build"))}}],a.initTable(e,s)}}});
//# sourceMappingURL=rtBuilders.js.map