import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const code=readFileSync(new URL('../advertising.js',import.meta.url),'utf8');
function fixture(overrides={}) {
 const dataset={host:'indexes.kymatalabs.com',approved:'true',consentReady:'true',slot:'6939405217',...overrides.dataset};
 const appended=[],elements=[],observers=[];
 const region={hidden:true,style:{},append(...els){elements.push(...els)}};
 const button={hidden:true,addEventListener(name,fn){this[name]=fn}};
 const document={currentScript:{dataset},head:{appendChild:s=>appended.push(s)},querySelector:s=>s==='[data-ad-privacy]'?button:region,createElement(tag){return {tag,style:{},attributes:{},setAttribute(k,v){this.attributes[k]=v},getBoundingClientRect(){return {width:800}}}}};
 const window={};if(!overrides.noObserver)window.IntersectionObserver=class{constructor(fn){this.fn=fn;observers.push(this)}observe(){}disconnect(){this.disconnected=true}};
 const location={hostname:'indexes.kymatalabs.com',pathname:'/',search:'',hash:'',...overrides.location};
 vm.runInNewContext(code,{window,document,location,URLSearchParams,IntersectionObserver:window.IntersectionObserver});
 return{window,region,button,appended,elements,observers,location};
}
test('all release gates fail closed without loading Google or exposing an empty placement',()=>{
 for(const options of [{dataset:{approved:'false'}},{dataset:{consentReady:'false'}},{dataset:{slot:''}},{location:{hostname:'preview.vercel.app'}},{location:{pathname:'/privacy.html'}},{location:{search:'?q=private+search'}},{location:{search:'?email=someone@example.com'}}]){
  const f=fixture(options);assert.equal(f.appended.length,0);assert.equal(f.region.hidden,true);assert.equal(f.window.adsbygoogle,undefined);
 }
});
test('eligible placement keeps geometry, requests near viewport once, and exposes a real CMP revocation action',()=>{
 const f=fixture();assert.equal(f.appended.length,1);assert.equal(f.appended[0].attributes['data-privacy-treatments'],'disablePersonalization');assert.equal(f.region.hidden,false);assert.match(f.region.style.cssText,/min-height:300px/);
 assert.equal(f.elements[0].textContent,'Advertisement');assert.equal(f.elements[1].attributes['data-ad-slot'],'6939405217');assert.equal(f.elements[1].attributes['data-restrict-data-processing'],'1');
 assert.equal(f.window.adsbygoogle,undefined);const ob=f.observers[0];ob.fn([{isIntersecting:true}]);ob.fn([{isIntersecting:true}]);assert.equal(f.window.adsbygoogle.length,1);assert.equal(ob.disconnected,true);
 let revoked=0;f.window.googlefc.showRevocationMessage=()=>revoked++;
 f.window.googlefc.callbackQueue[0].CONSENT_API_READY();assert.equal(f.button.hidden,false);f.button.click();assert.equal(revoked,1);
});
test('unsupported observers still request at most one ad without breaking content',()=>{const f=fixture({noObserver:true});assert.equal(f.window.adsbygoogle.length,1)});

test('only exact debug pairs permit messaging and never manual units',()=>{
 for(const type of ['gdpr','ccpa','usnat','usfl']){const f=fixture({location:{search:'?fc=alwaysshow&fctype='+type}});assert.equal(f.appended.length,1);assert.equal(f.elements.length,0);assert.equal(f.region.hidden,true)}
 for(const location of [{search:'?fc=private'},{search:'?fctype=gdpr'},{search:'?fc=alwaysshow&fctype=private'},{search:'?fc=alwaysshow&fc=alwaysshow&fctype=gdpr'},{search:'?utm_id=private'},{hash:'#private'}])assert.equal(fixture({location}).appended.length,0);
});
test('delayed viewport callbacks recheck a changed private URL',()=>{const f=fixture();f.location.search='?q=private';f.observers[0].fn([{isIntersecting:true}]);assert.equal(f.window.adsbygoogle,undefined)});
