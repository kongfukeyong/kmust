#!/usr/bin/env python3
"""Keep structurally suspicious questions out of the default practice corpus.

Run extract_validate.py DATA first, then this script, then validate DATA again.
The original extraction and all audit warnings are preserved alongside results.
Idempotent: subsequent runs reuse the preserved original corpus and audit.
"""
import argparse,collections,json,pathlib

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def write(p,o): p.write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('data',type=pathlib.Path);args=ap.parse_args();d=args.data
 required=('questions.json','resources.json','extraction-report.json','validation-report.json')
 for n in required:
  if not (d/n).is_file():raise SystemExit('Required file missing: '+n)
 all_path=d/'questions-all.json';audit_path=d/'validation-all-report.json';report_path=d/'extraction-report-all.json';resources_path=d/'resources-all.json'
 # Preserve the first raw run, including resource thumbnails and source metadata.
 if not all_path.exists():write(all_path,read(d/'questions.json'))
 if not audit_path.exists():write(audit_path,read(d/'validation-report.json'))
 if not report_path.exists():write(report_path,read(d/'extraction-report.json'))
 if not resources_path.exists():write(resources_path,read(d/'resources.json'))
 all_questions=read(all_path);audit=read(audit_path);report=read(report_path);resources=read(resources_path)
 if audit.get('errors'):raise SystemExit('Fix relational validation errors before quarantine.')
 ids={q['id'] for q in all_questions}
 reasons=collections.defaultdict(set)
 for warning in audit.get('warnings',[]):
  qid=warning.get('id')
  if qid not in ids:raise SystemExit('Audit refers to an unknown question: '+str(qid))
  reasons[qid].add(warning.get('reason','manual-review-required'))
 practice=[];review=[]
 for q in all_questions:
  if q['id'] in reasons:review.append(dict(q,quarantineReasons=sorted(reasons[q['id']])))
  else:practice.append(q)
 normal_count=collections.Counter(q['resourceId'] for q in practice);review_count=collections.Counter(q['resourceId'] for q in review)
 for resource in resources:
  rid=resource['id'];resource['rawQuestionCount']=normal_count[rid]+review_count[rid];resource['questionCount']=normal_count[rid];resource['reviewQuestionCount']=review_count[rid]
  if review_count[rid] and not normal_count[rid]:resource['status']='extracted-review-only'
 report.update({'rawQuestionCount':len(all_questions),'quarantinedCount':len(review),'questionCount':len(practice),'questionsWithAnswers':sum(q.get('answer') is not None for q in practice),'verifiedQuestions':sum(q.get('status')=='verified' for q in practice),'questionsByCourse':dict(collections.Counter(q['course'] for q in practice)),'resourcesByStatus':dict(collections.Counter(r['status'] for r in resources)),'quarantineReasons':dict(collections.Counter(reason for values in reasons.values() for reason in values)),'quarantinePolicy':'默认练习排除结构校验预警题；其余题仍为机器分离待校对，不代表答案正确性认证。','rawCorpusFile':'questions-all.json','reviewCorpusFile':'questions-review.json'})
 report.setdefault('notes',[]).append('结构校验发现异常的题目已单独放入questions-review.json；完整机器分题保存在questions-all.json，原始文件不变。')
 write(d/'questions.json',practice);write(d/'questions-review.json',review);write(d/'resources.json',resources);write(d/'extraction-report.json',report)
 summary={'rawQuestionCount':len(all_questions),'questionCount':len(practice),'quarantinedCount':len(review),'questionsWithAnswers':report['questionsWithAnswers'],'reasons':report['quarantineReasons'],'allIdsAccountedFor':len(practice)+len(review)==len(all_questions)}
 write(d/'quarantine-report.json',summary);print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
