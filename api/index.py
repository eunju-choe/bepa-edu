from flask import Flask, request, render_template, send_file
import pandas as pd
import os
import zipfile

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
    
    # 중복된 이름이 있는 데이터 추출 및 저장
    duplicated_names = df[df.duplicated(subset=['이름', '구분1(외부/내부)', '구분2(법정의무/직무역량)', '과정구분3', '과정명'], keep=False)]
    duplicated_names = duplicated_names.sort_values(by=['이름', '과정명'])
    duplicated_file_path = os.path.join(app.config['PROCESSED_FOLDER'], '1_과정명_일치.csv')
    duplicated_names.to_csv(duplicated_file_path, index=False, encoding='CP949')

    # 이름 개수 불일치 확인 및 저장
    name_counts = df.groupby('과정명')['이름'].agg(고유개수='nunique', 이름개수='count').reset_index()
    name_mismatch = name_counts[name_counts['이름개수'] != name_counts['고유개수']]
    mismatch_file_path = os.path.join(app.config['PROCESSED_FOLDER'], '2_이름_개수_불일치.csv')
    name_mismatch[['과정명', '고유개수', '이름개수']].to_csv(mismatch_file_path, index=False, encoding='CP949')

    # 띄어쓰기 제거 및 비교
    tmp1 = df.groupby('과정명').size().reset_index(name='연번')
    tmp1['과정명'] = tmp1['과정명'].str.replace(' ', '', regex=False)

    tmp2 = df.copy()
    tmp2['과정명'] = tmp2['과정명'].str.replace(' ', '', regex=False)
    tmp2 = tmp2.groupby('과정명').size().reset_index(name='연번')

    tmp = pd.merge(tmp1, tmp2, on='과정명', how='outer')
    tmp['일치 여부'] = tmp['연번_x'] == tmp['연번_y']
    comparison_file_path = os.path.join(app.config['PROCESSED_FOLDER'], '3_띄어쓰기_제거.csv')
    tmp[tmp['일치 여부'] == False].to_csv(comparison_file_path, index=False, encoding='CP949')

    # 모든 CSV 파일을 압축
    zip_file_path = os.path.join(app.config['PROCESSED_FOLDER'], 'processed_files.zip')
    with zipfile.ZipFile(zip_file_path, 'w') as zipf:
        zipf.write(duplicated_file_path, arcname='1_과정명_일치.csv')
        zipf.write(mismatch_file_path, arcname='2_이름_개수_불일치.csv')
        zipf.write(comparison_file_path, arcname='3_띄어쓰기_제거.csv')

    return render_template('download.html')

# 파일 다운로드
@app.route('/download/<int:file_id>')
def download_file(file_id):
    if file_id == 1:
        file_path = os.path.join(app.config['PROCESSED_FOLDER'], '1_과정명_일치.csv')
    elif file_id == 2:
        file_path = os.path.join(app.config['PROCESSED_FOLDER'], '2_이름_개수_불일치.csv')
    elif file_id == 3:
        file_path = os.path.join(app.config['PROCESSED_FOLDER'], '3_띄어쓰기_제거.csv')
    elif file_id == 4:
        file_path = os.path.join(app.config['PROCESSED_FOLDER'], 'processed_files.zip')
    else:
        return "잘못된 요청입니다."
    
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)