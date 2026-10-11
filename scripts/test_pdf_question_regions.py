import unittest
from pdf_question_regions import analyze_lines,detect_label

def line(text,y,x=55,size=12,x1=500):return {'text':text,'bbox':[x,y,x1,y+14],'size':size}
def normal():return [line('1. 第一题题干',90),line('A. 选项甲 B. 选项乙',125),line('2. 第二题题干',210),line('A. 第二题选项 B. 选项',250),line('3. 第三题题干',370)]

class RegionTests(unittest.TestCase):
 def test_clear_question_crop(self):
  r=analyze_lines(normal(),600,800,2);self.assertEqual(r['mode'],'crop');self.assertEqual(r['bbox'],[0,207,600,367])
 def test_decimal_formula_and_subquestion_not_labels(self):
  for text in ['1.23 m/s','(2) x+y=0','2. =x','0. 空白','2023. 年份']:self.assertIsNone(detect_label(text))
  self.assertEqual(detect_label('２．求加速度'),2)
 def test_small_superscript_and_center_formula_ignored(self):
  lines=normal()+[line('2. 公式',160,x=260),line('2. 上标',175,size=6)]
  self.assertEqual(analyze_lines(lines,600,800,2)['mode'],'crop')
 def test_repeated_question_number_falls_back(self):
  self.assertEqual(analyze_lines(normal()+[line('2. 参考答案',600)],600,800,2)['reason'],'ambiguous-repeated-question-label')
 def test_last_question_returns_page_and_continuation(self):
  r=analyze_lines(normal(),600,800,3);self.assertEqual(r['mode'],'page');self.assertTrue(r['continuationPossible'])
 def test_missing_middle_label_not_guessed(self):
  lines=normal();lines[-1]['text']='4. 第四题';self.assertEqual(analyze_lines(lines,600,800,2)['reason'],'nonconsecutive-next-label')
 def test_isolated_number_not_evidence(self):
  self.assertEqual(analyze_lines([line('2. 标签',210)],600,800,2)['mode'],'page')
 def test_graphic_crossing_crop_bottom_falls_back(self):
  self.assertEqual(analyze_lines(normal(),600,800,2,graphics=[[350,280,480,390]])['reason'],'graphic-crosses-question-boundary')
 def test_graphic_inside_question_is_retained(self):
  self.assertEqual(analyze_lines(normal(),600,800,2,graphics=[[350,240,480,340]])['mode'],'crop')
 def test_landscape_distinct_left_column(self):
  lines=[line('1. 题干一',60,x1=360),line('2. 题干二',180,x1=360),line('3. 题干三',310,x1=360),line('4. 题干四',60,x=465,x1=770),line('5. 题干五',180,x=465,x1=770),line('6. 题干六',310,x=465,x1=770)]
  r=analyze_lines(lines,840,590,2);self.assertEqual(r['mode'],'crop');self.assertEqual(r['bbox'][2],420)
 def test_landscape_gutter_crossing_rejected(self):
  lines=[line('1. 题干一',60,x1=360),line('2. 题干二',180,x1=360),line('3. 题干三',310,x1=360),line('跨栏长题干文字',210,x=60,x1=700)]
  self.assertEqual(analyze_lines(lines,840,590,2)['reason'],'text-crosses-column-gutter')
 def test_rotated_page_and_scan_fallback(self):
  self.assertEqual(analyze_lines(normal(),600,800,2,rotation=90)['mode'],'page');self.assertEqual(analyze_lines([],600,800,2)['mode'],'page')
 def test_noninteger_question_number_is_explicit_fallback(self):
  self.assertEqual(analyze_lines(normal(),600,800,'1-2')['reason'],'unsupported-question-number')

if __name__=='__main__':unittest.main()
