"""Validate extracted corpus relations and flag suspicious boundaries."""
import argparse,collections,json,pathlib,re
p=argparse.ArgumentParser();p.add_argument('data',type=pathlib.Path);a=p.parse_args()
resources=json.loads((a.data/'resources.json').read_text(encoding='utf-8'));questions=json.loads((a.data/'questions.json').read_text(encoding='utf-8'))
by_id={r['id']:r for r in resources};errors=[];warnings=[];counts=collections.Counter(q['resourceId'] for q in questions)
if len(by_id)!=len(resources):errors.append('Duplicate resource IDs')
if len({q['id'] for q in questions})!=len(questions):errors.append('Duplicate question IDs')
for q in questions:
 r=by_id.get(q['resourceId'])
 if not r:errors.append(q['id']+': resource missing');continue
 if q['sourcePath']!=r['path']:errors.append(q['id']+': source path mismatch')
 if q['course']!=r['course']:errors.append(q['id']+': course mismatch')
 if q['page'] is not None and (not isinstance(q['page'],int) or q['page']<1):errors.append(q['id']+': invalid page')
 if r['ext']!='pdf' and q['page'] is not None:errors.append(q['id']+': invented page')
 labels=[o['label'] for o in q['options']]
 if len(set(labels))!=len(labels):warnings.append({'id':q['id'],'reason':'duplicate-option-label','sourcePath':q['sourcePath']})
 if q['answer'] and re.fullmatch('[A-H]+',q['answer']) and labels and any(c not in labels for c in q['answer']):warnings.append({'id':q['id'],'reason':'answer-option-mismatch','sourcePath':q['sourcePath']})
 if len(q['stem'])>1600:warnings.append({'id':q['id'],'reason':'long-stem-review','sourcePath':q['sourcePath']})
 if re.search(r'[\ufffd\u0000]',q['stem']):warnings.append({'id':q['id'],'reason':'replacement-character','sourcePath':q['sourcePath']})
for r in resources:
 if r['questionCount']!=counts[r['id']]:errors.append(r['id']+': question count mismatch')
result={'resources':len(resources),'questions':len(questions),'errors':errors,'warnings':warnings,'passed':not errors}
(a.data/'validation-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'resources':len(resources),'questions':len(questions),'errors':len(errors),'warnings':len(warnings),'passed':not errors}))
raise SystemExit(bool(errors))
