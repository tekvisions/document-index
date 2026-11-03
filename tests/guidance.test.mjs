import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const code=readFileSync(new URL('../guidance.js',import.meta.url),'utf8');
function fixture({payload='{"/p/example":"Reviewed scope"}',href='/p/example/',existing=false,missing=false}={}){
 const callbacks=[],children=existing?[{className:'catalog-scope-note'}]:[];
 const anchor={getAttribute:()=>href,closest:()=>null,querySelector:()=>children.find(x=>x.className==='catalog-scope-note'),appendChild:x=>children.push(x)};
 const document={getElementById:id=>id==='catalog-scope-notes'?(missing?null:{textContent:payload}):id==='grid'?{querySelectorAll:()=>[anchor]}:null,createElement:()=>({})};
 vm.runInNewContext(code,{document,location:{href:'https://example.test/',origin:'https://example.test'},URL,MutationObserver:class{constructor(callback){callbacks.push(callback)}observe(){}}});
 return {children,callbacks};
}
test('missing optional payload leaves existing catalog unchanged',()=>{const f=fixture({missing:true});assert.equal(f.children.length,0);assert.equal(f.callbacks.length,0)});
test('untrusted note remains text and never becomes an HTML assignment',()=>{const f=fixture({payload:JSON.stringify({'/p/example':'<script>untrusted</script>'})});assert.equal(f.children[0].textContent,'Scope note: <script>untrusted</script>');assert.equal(f.children[0].innerHTML,undefined)});
test('rerenders preserve one note without rewriting catalog links',()=>{const f=fixture();f.callbacks[0]();f.callbacks[0]();assert.equal(f.children.length,1);assert.equal(f.children[0].className,'catalog-scope-note')});
test('external same-path links do not receive an internal scope note',()=>{assert.equal(fixture({href:'https://other.test/p/example/'}).children.length,0)});
test('malformed data fails quietly without diagnostics or observer work',()=>{const f=fixture({payload:'invalid'});assert.equal(f.children.length,0);assert.equal(f.callbacks.length,0)});
