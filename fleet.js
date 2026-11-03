/* Shared accessibility only: no analytics, network, storage or data mutations. */
(function(){
  "use strict";
  var initial=document.querySelector('.catalog-snapshot');
  var fallbackParent=initial&&initial.parentElement,fallbackHTML=fallbackParent?fallbackParent.innerHTML:null;
  var originalStats=Array.from(document.querySelectorAll('#metarow,#s-count,#s-cats,#s-top,#total,#edition')).map(function(node){return {node:node,html:node.innerHTML};});
  function controls(disabled){document.querySelectorAll('main input[type="search"],main .sort button,main button.sortable,main button.chip').forEach(function(control){control.disabled=disabled;});}
  window.addEventListener('catalog:ready',function(){controls(false);sync();});
  window.addEventListener('catalog:error',function(){
    if(fallbackParent&&fallbackHTML!==null)fallbackParent.innerHTML=fallbackHTML;
    originalStats.forEach(function(item){item.node.innerHTML=item.html;});
    controls(true);
  });
  function sync(){
    document.querySelectorAll('button.chip,.sort button,button.sortable').forEach(function(button){
      var direction=button.getAttribute('data-sort-direction');
      var selected=direction?direction!=="none":button.classList.contains('active')||button.classList.contains('on');
      button.setAttribute('aria-pressed',String(selected));
      if(direction){
        var label=button.textContent.replace(/[▲▼↑↓]/g,'').trim();
        button.setAttribute('aria-label',label+(selected?', sorted '+direction:', sort'));
      }
    });
  }
  var status=document.querySelector('#metaline,#count,#resultcount');
  if(status){status.setAttribute('role','status');status.setAttribute('aria-live','polite');status.setAttribute('aria-atomic','true');}
  var search=document.querySelector('input[type="search"]'),results=document.querySelector('#grid,#rows,#board,#lboard');
  if(search&&results){search.setAttribute('aria-controls',results.id);}
  document.addEventListener('click',function(){queueMicrotask(sync);});
  document.querySelectorAll('#chips,#filters,#toggles,#sort').forEach(function(control){
    new MutationObserver(sync).observe(control,{childList:true,subtree:true});
  });
  sync();
})();
