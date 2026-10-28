import {escapeHTML as e} from './core.mjs';

const arrow='<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m6 8 4 4 4-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const check='<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m5 10 3 3 7-7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
let active=null,focusAfterChange=null;
export function selectOptionMarkup(options,selectedIndex){
 return options.map((option,index)=>`<button type="button" role="option" data-select-index="${index}" aria-selected="${index===selectedIndex}" ${option.disabled?'disabled aria-disabled="true"':''} title="${e(option.label)}"><span>${e(option.label)}</span>${index===selectedIndex?check:''}</button>`).join('');
}
function close(focus=false){
 if(!active)return;
 const {button,menu}=active;active=null;
 button.setAttribute('aria-expanded','false');menu.remove();
 if(focus&&button.isConnected)button.focus();
}
function focusOption(menu,index){
 const option=menu.querySelectorAll('[role=option]:not(:disabled)')[index];
 if(option){option.focus({preventScroll:true});option.scrollIntoView({block:'nearest'});}
}
function update(select,button){
 const label=select.selectedOptions[0]?.label||'请选择';
 button.querySelector('span').textContent=label;button.title=label;button.disabled=select.disabled;
}
function open(select,button){
 close();if(select.disabled||select.closest('[inert]'))return;
 const menu=document.createElement('div');menu.className='ui-select-menu';menu.id=button.getAttribute('aria-controls');menu.setAttribute('role','listbox');menu.setAttribute('aria-label',button.getAttribute('aria-label'));
 menu.innerHTML=selectOptionMarkup([...select.options].map(option=>({label:option.label,disabled:option.disabled})),select.selectedIndex);
 (select.closest('.agione-demo') || document.body).append(menu);active={select,button,menu};button.setAttribute('aria-expanded','true');
 const r=button.getBoundingClientRect(),width=Math.min(Math.max(r.width,220),innerWidth-24),below=innerHeight-r.bottom-12,above=r.top-12,up=below<180&&above>below;
 Object.assign(menu.style,{width:width+'px',left:Math.max(12,Math.min(r.left,innerWidth-width-12))+'px',maxHeight:Math.max(64,Math.min(300,up?above:below))+'px'});
 if(up)menu.style.bottom=(innerHeight-r.top+6)+'px';else menu.style.top=(r.bottom+6)+'px';
 menu.addEventListener('click',event=>{
  const option=event.target.closest('[data-select-index]');if(!option||option.disabled)return;
  const index=Number(option.dataset.selectIndex),changed=select.selectedIndex!==index;
  select.selectedIndex=index;update(select,button);close(true);
  if(changed){focusAfterChange=select.id;select.dispatchEvent(new Event('change',{bubbles:true}));}
 });
 menu.addEventListener('keydown',event=>{
  const options=[...menu.querySelectorAll('[role=option]:not(:disabled)')],at=options.indexOf(document.activeElement);
  if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){
   event.preventDefault();focusOption(menu,event.key==='Home'?0:event.key==='End'?options.length-1:(at+(event.key==='ArrowDown'?1:-1)+options.length)%options.length);
  }else if(event.key==='Escape'){event.preventDefault();close(true);}
  else if(event.key==='Tab')close(true);
  else if(event.key.length===1&&!event.ctrlKey&&!event.metaKey&&!event.altKey&&event.key!==' '){
   const next=options.findIndex((option,index)=>index>at&&option.textContent.trim().toLowerCase().startsWith(event.key.toLowerCase()));
   const first=next<0?options.findIndex(option=>option.textContent.trim().toLowerCase().startsWith(event.key.toLowerCase())):next;
   if(first>=0){event.preventDefault();focusOption(menu,first);}
  }
 });
 const enabled=[...menu.querySelectorAll('[role=option]:not(:disabled)')],index=enabled.findIndex(option=>Number(option.dataset.selectIndex)===select.selectedIndex);
 focusOption(menu,Math.max(0,index));
}
export function enhanceSelects(root){
 if(active&&(!active.select.isConnected||root.inert))close();
 for(const select of root.querySelectorAll('.workspace-tools select')){
  let button=select._menuButton;
  if(!button){
   const label=[...(select.labels?.[0]?.childNodes||[])].filter(node=>node.nodeType===3).map(node=>node.textContent.trim()).join(' ')||'选择选项';
   const wrapper=document.createElement('span');wrapper.className='ui-select';select.before(wrapper);wrapper.append(select);select.hidden=true;
   button=document.createElement('button');button.type='button';button.className='ui-select-trigger';button.id=select.id+'Trigger';button.setAttribute('role','combobox');button.setAttribute('aria-label',label);button.setAttribute('aria-haspopup','listbox');button.setAttribute('aria-controls',select.id+'Menu');button.setAttribute('aria-expanded','false');button.innerHTML='<span></span>'+arrow;wrapper.append(button);select._menuButton=button;
   button.addEventListener('click',()=>active?.select===select?close():open(select,button));
   button.addEventListener('keydown',event=>{if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){event.preventDefault();open(select,button);if(active&&event.key==='Home')focusOption(active.menu,0);if(active&&event.key==='End')focusOption(active.menu,active.menu.querySelectorAll('[role=option]:not(:disabled)').length-1);}});
  }
  update(select,button);
 }
 if(focusAfterChange&&!root.inert){
  [...root.querySelectorAll('select')].find(node=>node.id===focusAfterChange)?._menuButton?.focus({preventScroll:true});focusAfterChange=null;
 }
}
if(typeof document!=='undefined'){
 document.addEventListener('pointerdown',event=>{if(active&&!active.menu.contains(event.target)&&!active.button.contains(event.target))close();});
 window.addEventListener('resize',()=>close());
 window.addEventListener('scroll',event=>{if(active&&!(event.target instanceof Node&&active.menu.contains(event.target)))close();},true);
}

export function closeSelectMenus(root){if(active&&(!root||root.contains(active.select)||!active.select.isConnected))close();}
