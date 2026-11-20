// Asignaciones de zonas (RSA) del AUP/UUP europeo vigente (EUROCONTROL NOP, portal público).
// Abre el último EAUP/EUUP de cada periodo (hoy y mañana) y guarda las zonas LE/LP en data/aup.json.
const {chromium}=require('playwright-core');const fs=require('fs');
const URL='https://www.public.nm.eurocontrol.int/PUBPORTAL/gateway/spec/index.html';
const dt=s=>{const m=s.match(/(\d\d)\/(\d\d)\/(\d{4}) (\d\d):(\d\d)/);return m?Date.UTC(+m[3],m[2]-1,+m[1],+m[4],+m[5]):0;};
(async()=>{
  const b=await chromium.launch({executablePath:process.env.CHROME||'/usr/bin/google-chrome',args:['--no-sandbox']});
  const ctx=await b.newContext({viewport:{width:1400,height:1000}});const p=await ctx.newPage();
  await p.goto(URL,{waitUntil:'networkidle',timeout:120000});await p.waitForTimeout(5000);
  // filas del cuadro «European AUP/UUP»: tipo, inicio y fin; la primera de cada fin de validez es la más reciente
  const pick=()=>p.evaluate(()=>{const rows=[...document.querySelectorAll('tr')].filter(tr=>/^\s*E(AUP|UUP)\s/.test(tr.innerText)&&(tr.innerText.match(/\d\d\/\d\d\/\d{4} \d\d:\d\d/g)||[]).length>=2&&tr.querySelectorAll('tr').length===0);
    const seen={},out=[];rows.forEach((tr,i)=>{const d=tr.innerText.match(/\d\d\/\d\d\/\d{4} \d\d:\d\d/g);const til=d[d.length-1];if(!seen[til]){seen[til]=1;out.push({i,txt:tr.innerText.replace(/\s+/g,' ').trim()});}});
    window.__rows=rows;return out;});
  const targets=(await pick()).slice(0,3);
  console.log('Publicaciones a leer:',targets.map(t=>t.txt).join(' | '));
  const plans={};
  for(const t of targets){
    await pick();
    const h=await p.evaluateHandle(i=>{const tr=window.__rows[i];return [...tr.querySelectorAll('a,div,span,td')].find(e=>e.children.length===0&&/^\d\d\/\d\d\/\d{4} \d\d:\d\d$/.test(e.innerText.trim()));},t.i);
    if(!h.asElement()){console.log('Sin enlace',t.txt);continue;}
    const [q]=await Promise.all([ctx.waitForEvent('page',{timeout:30000}).catch(()=>null),h.asElement().click()]);
    if(!q)continue;
    try{
      await q.waitForLoadState('networkidle',{timeout:60000}).catch(()=>{});await q.waitForTimeout(4000);
      const info=await q.evaluate(()=>{const m=document.body.innerText.match(/Type\s+(\S+)\s+Valid WEF\s+(\S+ \S+)\s+Valid TIL\s+(\S+ \S+)\s+Released On\s+(\S+ \S+)/);return m?m.slice(1):null;});
      if(!info){console.log('Sin cabecera');continue;}
      const [type,wef,til,rel]=info;
      if(plans[wef]){console.log('Ya tengo',wef);continue;}
      await q.click('text=RSA Allocations').catch(()=>{});await q.waitForTimeout(2500);
      const rows=await q.evaluate(()=>[...document.querySelectorAll('tr[id*="RSA_ALLOCATION_TABLE-"]')].map(tr=>{const c=k=>{const td=tr.querySelector(`td[id*="-${k}_COLUMN-"]`);return td?td.innerText.replace(/\u00a0/g,' ').trim():'';};
        return {id:c('RSA'),notam:c('NOTAM'),rmk:c('REMARK'),flMin:c('MNM_FL'),flMax:c('MAX_FL'),ftMin:c('MNM_FT'),ftMax:c('MAX_FT'),wef:c('WEF'),unt:c('UNT')};}).filter(r=>/^L[EP]/.test(r.id)));
      const w0=dt(wef);
      const abs=t=>{const m=t.match(/(\d\d):(\d\d)/);if(!m)return null;let x=Date.UTC(new Date(w0).getUTCFullYear(),new Date(w0).getUTCMonth(),new Date(w0).getUTCDate(),+m[1],+m[2]);if(x<w0)x+=864e5;return x;};
      plans[wef]={type,wef:w0,til:dt(til),released:dt(rel),rsa:rows.map(r=>({id:r.id,from:abs(r.wef),to:(()=>{let t=abs(r.unt);const f=abs(r.wef);if(t!==null&&f!==null&&t<=f)t+=864e5;return t;})(),
        fl:[r.flMin,r.flMax],ft:[r.ftMin,r.ftMax],rmk:r.rmk})).filter(r=>r.from!==null)};
      console.log(type,wef,'→',til,'publicado',rel,'·',plans[wef].rsa.length,'asignaciones LE/LP');
    }finally{await q.close();}
  }
  await b.close();
  const out={fetched:Math.floor(Date.now()/1000),source:'EUROCONTROL NOP (AUP/UUP)',plans:Object.values(plans).sort((a,b)=>a.wef-b.wef)};
  if(!out.plans.length){console.log('Sin AUP/UUP');return;}
  const f='data/aup.json';let old=null;try{old=JSON.parse(fs.readFileSync(f,'utf8'));}catch(e){}
  fs.writeFileSync(f,JSON.stringify(out));
  console.log(old&&JSON.stringify(old.plans)===JSON.stringify(out.plans)?'AUP sin cambios (hora de consulta actualizada)':'aup.json guardado');
})().catch(e=>{console.error('AUP falló:',e.message);process.exit(0);});
