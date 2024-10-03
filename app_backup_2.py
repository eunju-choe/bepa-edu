from flask import Flask, request, render_template
import pandas as pd
import os

app = Flask(__name__)

# 업로드 경로 설정
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

# 폴더 생성
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# 메인 페이지
@app.route('/')
def index():
    return render_template('index.html')

# 파일 업로드 및 처리
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "파일이 없습니다."
    
    file = request.files['file']
    if file.filename == '':
        return "파일 이름이 없습니다."
    
    # CSV 파일 저장
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)
    
    # CSV 파일 처리
    df = pd.read_csv(file_path, encoding='CP949', skiprows=1)
    df = df.dropna(subset=['연번', '이름']).drop(columns=['비고1', '비고2', 'Unnamed: 14'])
    df = df.rename(columns={'교육\n일시': '교육일시', '교육\n시간': '교육시간'})
    df[['연번', '교육시간']] = df[['연번', '교육시간']].astype('int')
    
    # 중복된 이름이 있는 데이터 추출
    duplicated_names = df[df.duplicated(subset=['이름', '구분1(외부/내부)', '구분2(법정의무/직무역량)', '과정구분3', '과정명'], keep=False)]
    duplicated_names = duplicated_names.sort_values(by=['이름', '과정명'])

    # 이름 개수 불일치 확인
    name_counts = df.groupby('과정명')['이름'].agg(고유개수='nunique', 이름개수='count').reset_index()
    name_mismatch = name_counts[name_counts['이름개수'] != name_counts['고유개수']]

    # 띄어쓰기 제거 및 비교
    tmp1 = df.groupby('과정명').size().reset_index(name='연번')
    tmp1['과정명'] = tmp1['과정명'].str.replace(' ', '', regex=False)

    tmp2 = df.copy()
    tmp2['과정명'] = tmp2['과정명'].str.replace(' ', '', regex=False)
    tmp2 = tmp2.groupby('과정명').size().reset_index(name='연번')

    tmp = pd.merge(tmp1, tmp2, on='과정명', how='outer')
    tmp['일치 여부'] = tmp['연번_x'] == tmp['연번_y']

    # 처리된 데이터프레임을 HTML로 변환하여 보여주기
    return render_template('result.html', 
                           duplicated_names=duplicated_names.to_html(index=False),
                           name_mismatch=name_mismatch[['과정명', '고유개수', '이름개수']].to_html(index=False),
                           comparison=tmp[tmp['일치 여부'] == False].to_html(index=False))

if __name__ == '__main__':
    app.run(debug=True)