from flask import Flask, request, render_template, send_file # type: ignore
import pandas as pd # type: ignore
import os
import re

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
    try:
        df = pd.read_csv(file_path, encoding='CP949', skiprows=1)
    except Exception as e:
        return f"CSV 파일을 처리하는 중 오류가 발생했습니다: {str(e)}"
    
    df = df.dropna(subset=['연번', '이름']).drop(columns=['비고1', '비고2', 'Unnamed: 14'])
    df = df.rename(columns={'교육\n일시': '교육일시', '교육\n시간': '교육시간'})
    df[['연번', '교육시간']] = df[['연번', '교육시간']].astype('int')
    
    # 체크박스 선택 여부 확인
    include_date = request.form.get('include_date') == 'yes'

    # 중복된 이름이 있는 데이터 추출 (체크박스 선택 시 '교육일시' 포함)
    subset_columns = ['이름', '구분1(외부/내부)', '구분2(법정의무/직무역량)', '과정구분3', '과정명']
    if include_date:
        subset_columns.append('교육일시')

    duplicated_names = df[df.duplicated(subset=subset_columns, keep=False)]
    duplicated_names = duplicated_names.sort_values(by=['이름', '과정명'])

    # 이름 개수 불일치 확인
    name_counts = df.groupby('과정명')['이름'].agg(고유개수='nunique', 이름개수='count').reset_index()
    name_mismatch = name_counts[name_counts['이름개수'] != name_counts['고유개수']]

    # 공백과 괄호 제거 전 후 비교
    space_yes = df.groupby('과정명').size().reset_index(name='띄어쓰기 제거 전')
    space_yes['과정명'] = space_yes['과정명'].str.replace(' ', '', regex=False)

    bracket_yes = space_yes.groupby('과정명').sum().reset_index()
    bracket_yes.columns = ['과정명', '괄호 제거 전']
    bracket_yes['과정명'] = bracket_yes['과정명'].apply(lambda x:re.sub(r'\(\d+(차시|시간)\)', '', x))

    space_no = df.copy()
    space_no['과정명'] = space_no['과정명'].str.replace(' ', '', regex=False)
    space_no = space_no.groupby('과정명').size().reset_index(name='띄어쓰기 제거 후')

    bracket_no = space_no.copy()
    bracket_no['과정명'] = bracket_no['과정명'].apply(lambda x: re.sub(r'\(\d+(차시|시간)\)', '', x))
    bracket_no = bracket_no.groupby('과정명').sum().reset_index()
    bracket_no.columns = ['과정명', '괄호 제거 후']

    space_df = pd.merge(space_yes, space_no, on='과정명', how='outer')
    space_df['일치 여부'] = space_df['띄어쓰기 제거 전'] == space_df['띄어쓰기 제거 후']
    space_df = space_df[space_df['일치 여부'] == False]
    space_df = space_df.groupby('과정명').agg({
        "띄어쓰기 제거 전" : lambda x: ", ".join(map(str, x)),
        "띄어쓰기 제거 후" : "first"
    }).reset_index()
    space_df.colmns = ['과정명', '구분 별 개수', '전체 개수']

    bracket_df = pd.merge(bracket_yes, bracket_no, on='과정명', how='outer')
    bracket_df['일치 여부'] = bracket_df['괄호 제거 전'] == bracket_df['괄호 제거 후']
    bracket_df = bracket_df[bracket_df['일치 여부'] == False]
    bracket_df = bracket_df.groupby('과정명').agg({
        "괄호 제거 전" : lambda x: ", ".join(map(str, x)),
        "괄호 제거 후" : "first"
    }).reset_index()
    bracket_df.colmns = ['과정명', '구분 별 개수', '전체 개수']

    # 파일 저장 경로 설정
    duplicated_file = os.path.join(app.config['PROCESSED_FOLDER'], 'duplicated_names.csv')
    mismatch_file = os.path.join(app.config['PROCESSED_FOLDER'], 'name_mismatch.csv')
    space_comparison_file = os.path.join(app.config['PROCESSED_FOLDER'], 'space_comparison.csv')
    bracket_comparison_file = os.path.join(app.config['PROCESSED_FOLDER'], 'bracket_comparison.csv')

    # 처리된 데이터 저장
    duplicated_names.to_csv(duplicated_file, index=False, encoding='CP949')
    name_mismatch[['과정명', '고유개수', '이름개수']].to_csv(mismatch_file, index=False, encoding='CP949')
    space_df.to_csv(space_comparison_file, index=False, encoding='CP949')
    bracket_df.to_csv(bracket_comparison_file, index=False, encoding='CP949')

    # 처리된 데이터프레임을 HTML로 변환하여 보여주기
    return render_template('result.html', 
                           duplicated_names=duplicated_names.to_html(index=False, escape=False),
                           name_mismatch=name_mismatch[['과정명', '고유개수', '이름개수']].to_html(index=False, escape=False),
                           space_comparison=space_df.to_html(index=False, escape=False),
                           bracket_comparison=bracket_df.to_csv(index=False, escape=False),
                           duplicated_file='duplicated_names.csv',
                           mismatch_file='name_mismatch.csv',
                           space_comparison_file='space_comparison.csv',
                           bracket_comparison_file='bracket_comparison.csv')

# 파일 다운로드 처리
@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)