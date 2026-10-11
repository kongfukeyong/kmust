'use strict';
// All formula engines and media are served locally, including the APK offline copy.
window.MathJax={startup:{typeset:false},options:{enableMenu:false},svg:{fontCache:'local'}};
const mathTags=new Set('math mrow mi mn mo mtext mspace mfrac msqrt mroot msup msub msubsup munder mover munderover mfenced mtable mtr mtd menclose mstyle mpadded mphantom mmultiscripts mprescripts none semantics'.split(' '));
const mathAttrs=new Set('display mathvariant stretchy symmetric largeop movablelimits accent accentunder fence separator form lspace rspace linethickness bevelled notation columnalign rowalign columnspacing rowspacing columnspan rowspan open close separators width height depth voffset scriptlevel displaystyle'.split(' '));
function safeMath(source){
  const xml=new DOMParser().parseFromString(source,'application/xml');
  if(xml.querySelector('parsererror')||xml.documentElement.localName!=='math')return '';
  function copy(n){
    if(n.nodeType===3)return document.createTextNode(n.textContent);
    if(n.nodeType!==1||!mathTags.has(n.localName))return document.createTextNode('');
    const e=document.createElementNS('http://www.w3.org/1998/Math/MathML',n.localName);
    for(const a of n.attributes)if(mathAttrs.has(a.localName)&&a.value.length<100&&!/[<>]/.test(a.value))e.setAttribute(a.localName,a.value);
    for(const c of n.childNodes)e.append(copy(c));return e;
  }
  return new XMLSerializer().serializeToString(copy(xml.documentElement));
}
function richText(text,segments){
  const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const plain=s=>escape(s).replace(/\[pic\]|【pic】/gi,'<span class="missing-formula">〔公式或图形待恢复，请查看原卷〕</span>');
  if(!Array.isArray(segments)||!segments.length)return plain(text);
  return segments.map(s=>{
    if(s.type==='text')return plain(s.text);
    if(s.type==='math'){const m=safeMath(s.mathml||'');return m?`<span class="math-inline">${m}</span>`:plain(s.linearText||'〔公式待恢复〕');}
    if(s.type==='image'&&/^math-media\/[a-zA-Z0-9_.-]+$/.test(s.src||''))return `<a class="formula-image-link" href="${escape(s.src)}" target="_blank" rel="noopener"><img class="formula-image" src="${escape(s.src)}" alt="${escape(s.alt||'原文公式或图形，点按可放大')}" ${s.width?`style="width:${Math.min(1200,Math.max(16,Number(s.width)||100))}px"`:''} loading="lazy"></a>`;
    return '<span class="missing-formula">〔原文对象待恢复，请查看原卷〕</span>';
  }).join('');
}
let mathQueue=Promise.resolve();
function typesetMath(root){
  mathQueue=mathQueue.then(async()=>{if(!root?.isConnected)return;await window.MathJax?.startup?.promise;if(window.MathJax?.typesetPromise)await MathJax.typesetPromise([root]);}).catch(()=>{});
}
function clearMath(root){if(window.MathJax?.typesetClear)MathJax.typesetClear([root]);}
document.addEventListener('click',event=>{
  const link=event.target.closest('.formula-image-link');if(!link)return;
  event.preventDefault();
  const viewer=document.createElement('dialog');viewer.className='image-viewer';viewer.setAttribute('aria-label','原文公式或图形');
  const close=document.createElement('button');close.className='button secondary';close.textContent='关闭放大图';close.onclick=()=>viewer.close();
  const img=document.createElement('img');img.src=link.querySelector('img').src;img.alt='从原文件提取的公式或图形';
  const toolbar=document.createElement('div');toolbar.className='image-viewer-toolbar';
  const canvas=document.createElement('div');canvas.className='image-viewer-canvas';
  const zoomIn=document.createElement('button');zoomIn.className='button secondary';zoomIn.textContent='＋ 放大';
  const zoomOut=document.createElement('button');zoomOut.className='button secondary';zoomOut.textContent='－ 缩小';
  const scale=document.createElement('span');scale.className='image-viewer-scale';scale.setAttribute('aria-live','polite');let zoom=1;
  function updateZoom(){img.style.width=(zoom*100)+'%';scale.textContent=Math.round(zoom*100)+'%';zoomOut.disabled=zoom<=1;zoomIn.disabled=zoom>=4;}
  zoomIn.onclick=()=>{zoom=Math.min(4,zoom+.5);updateZoom()};zoomOut.onclick=()=>{zoom=Math.max(1,zoom-.5);updateZoom()};updateZoom();
  toolbar.append(close,zoomOut,zoomIn,scale);canvas.append(img);viewer.append(toolbar,canvas);document.body.append(viewer);viewer.addEventListener('close',()=>viewer.remove());viewer.showModal();
});
