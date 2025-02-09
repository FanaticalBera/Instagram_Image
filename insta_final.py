import streamlit as st
import instaloader
import os
import zipfile
from PIL import Image
import tempfile
import shutil
from datetime import datetime
import requests
from io import BytesIO

def download_media_to_memory(url):
    """URL에서 미디어를 다운로드하여 메모리에 저장"""
    response = requests.get(url)
    return BytesIO(response.content)

def create_zip_in_memory(files_dict):
    """메모리에서 ZIP 파일 생성"""
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_name, file_content in files_dict.items():
            zip_file.writestr(file_name, file_content.getvalue())
    zip_buffer.seek(0)
    return zip_buffer

def get_post_nodes(post):
    """포스트의 미디어 노드를 가져옴 (단일 및 다중 게시물 모두 처리)"""
    if post.typename == 'GraphImage':  # 단일 이미지
        return [post]
    elif post.typename == 'GraphSidecar':  # 여러 이미지
        return list(post.get_sidecar_nodes())
    elif post.typename == 'GraphVideo':  # 단일 비디오
        return [post]
    return []

def get_media_url(node):
    """노드에서 미디어 URL을 가져옴"""
    if hasattr(node, 'video_url') and node.is_video:
        return node.video_url
    if hasattr(node, 'display_url'):
        return node.display_url
    # Post 객체인 경우 (단일 미디어)
    if hasattr(node, 'url'):
        return node.url
    return None

def is_video(node):
    """노드가 비디오인지 확인"""
    return hasattr(node, 'is_video') and node.is_video

def get_thumbnail_url(node):
    """비디오 썸네일 URL 가져오기"""
    if hasattr(node, 'thumbnail_url'):
        return node.thumbnail_url
    if hasattr(node, 'display_url'):
        return node.display_url
    return None


def download_post_media(post):
    """포스트의 모든 미디어를 다운로드하여 딕셔너리로 반환"""
    media_files = {}
    nodes = get_post_nodes(post)
    for idx, node in enumerate(nodes):
        url = get_media_url(node)
        if url:
            file_content = download_media_to_memory(url)
            extension = '.mp4' if is_video(node) else '.jpg'
            file_name = f'instagram_media_{idx}{extension}'
            media_files[file_name] = file_content
    return media_files

def display_media_preview(node):
    """미디어 프리뷰 표시"""
    if is_video(node):
        # 비디오인 경우 썸네일 표시
        thumbnail_url = get_thumbnail_url(node)
        if thumbnail_url:
            try:
                response = requests.get(thumbnail_url)
                image = Image.open(BytesIO(response.content))
                st.image(image, use_column_width=True, caption="🎥 비디오")
                return True
            except Exception as e:
                st.error(f"비디오 썸네일 로드 실패: {str(e)}")
                st.write("🎥 비디오 파일")
                return True
    else:
        # 이미지인 경우 기존 방식대로 표시
        url = get_media_url(node)
        if url:
            try:
                response = requests.get(url)
                image = Image.open(BytesIO(response.content))
                st.image(image, use_column_width=True, caption="이미지")
                return True
            except Exception as e:
                st.error(f"미디어 로드 실패: {str(e)}")
                return False
    return False

def reset_app():
    """앱의 세션 상태를 초기화"""
    for key in st.session_state.keys():
        del st.session_state[key]
    # URL 입력 필드 초기화를 위한 상태 추가
    st.session_state.url_input = ""
    st.session_state.show_content = False

def main():
    st.set_page_config(page_title="Instagram 다운로더", layout="wide")
    
    # 앱 스타일링
    st.markdown("""
        <style>
        .stButton>button {
            width: 100%;
            border-radius: 5px;
            height: 3em;
        }
        .download-count {
            font-size: 1.2em;
            font-weight: bold;
            color: #1DB954;
        }
        .stCheckbox {
            margin-top: 0.5em;
        }
        .success-message {
            padding: 1em;
            border-radius: 0.5em;
            background-color: #d4edda;
            color: #155724;
            margin: 1em 0;
        }            
        </style>
    """, unsafe_allow_html=True)

    if 'url_input' not in st.session_state:
        st.session_state.url_input = ""
    if 'show_content' not in st.session_state:
        st.session_state.show_content = False

    # 다운로드 완료 상태 초기화
    if 'download_completed' not in st.session_state:
        st.session_state.download_completed = False

    # 세션 상태 초기화
    if 'selected_files' not in st.session_state:
        st.session_state.selected_files = set()
    if 'media_nodes' not in st.session_state:
        st.session_state.media_nodes = []
    
    # 헤더
    st.title("🎯 Instagram 다운로더")
    st.markdown("---")
    
     # URL 입력 필드
    post_url = st.text_input("Instagram 포스트 URL을 입력하세요",
                            value=st.session_state.url_input,
                            placeholder="https://www.instagram.com/p/...",
                            key="url_input",
                            on_change=lambda: setattr(st.session_state, 'show_content', True))
    
    # URL 입력 필드 아래 버튼 추가
    st.button("미디어 불러오기", on_click=lambda: setattr(st.session_state, 'show_content', True))

    # URL이 입력되고 show_content가 True일 때만 콘텐츠 표시
    if post_url and st.session_state.show_content:
        try:
            # Instaloader 초기화 및 포스트 가져오기
            L = instaloader.Instaloader()
            post = instaloader.Post.from_shortcode(L.context, post_url.split("/")[-2])
            
            # 미디어 노드 저장
            st.session_state.media_nodes = get_post_nodes(post)
            
            # 다운로드 모드 선택
            st.markdown("### 다운로드 모드 선택")
            tab1, tab2 = st.tabs(["📥 전체 다운로드", "✨ 선택 다운로드"])
            
            with tab1:
                if st.button("전체 다운로드", key="full_download"):
                    with st.spinner("다운로드 중..."):
                        media_files = download_post_media(post)
                        if media_files:
                            zip_buffer = create_zip_in_memory(media_files)
                            st.download_button(
                                label="ZIP 파일 다운로드",
                                data=zip_buffer,
                                file_name="instagram_downloads.zip",
                                mime="application/zip",
                                on_click=lambda: setattr(st.session_state, 'download_completed', True)
                            )
                            st.session_state.download_completed = True
                        else:
                            st.error("다운로드할 미디어를 찾을 수 없습니다.")
            
            with tab2:
                # 전체 선택/해제 버튼
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("전체 선택", key="select_all"):
                        st.session_state.selected_files = set(range(len(st.session_state.media_nodes)))
                        st.experimental_rerun()
                
                with col2:
                    if st.button("전체 해제", key="deselect_all"):
                        st.session_state.selected_files.clear()
                        st.experimental_rerun()
                
                # 미디어 그리드 표시
                cols = st.columns(4)
                for idx, node in enumerate(st.session_state.media_nodes):
                    with cols[idx % 4]:
                        if display_media_preview(node):
                            # 선택 체크박스
                            if st.checkbox(f"선택 {idx + 1}", 
                                         value=idx in st.session_state.selected_files,
                                         key=f"select_{idx}"):
                                st.session_state.selected_files.add(idx)
                            else:
                                st.session_state.selected_files.discard(idx)
                
                # 선택된 파일 수 표시
                selected_count = len(st.session_state.selected_files)
                st.markdown(f"""
                    <div class='download-count'>
                        선택된 파일: {selected_count}개
                    </div>
                """, unsafe_allow_html=True)
                
                # 선택 다운로드 버튼
                if selected_count > 0:
                    if st.button(f"{selected_count}개 파일 다운로드"):
                        with st.spinner("선택한 파일 다운로드 중..."):
                            selected_media_files = {}
                            for idx in st.session_state.selected_files:
                                node = st.session_state.media_nodes[idx]
                                url = get_media_url(node)
                                if url:
                                    file_content = download_media_to_memory(url)
                                    extension = '.mp4' if is_video(node) else '.jpg'
                                    file_name = f'instagram_media_{idx}{extension}'
                                    selected_media_files[file_name] = file_content
                            
                            if selected_media_files:
                                zip_buffer = create_zip_in_memory(selected_media_files)
                                st.download_button(
                                    label="선택한 파일 다운로드 (ZIP)",
                                    data=zip_buffer,
                                    file_name="instagram_selected_downloads.zip",
                                    mime="application/zip",
                                    on_click=lambda: setattr(st.session_state, 'download_completed', True)
                                )
                                st.session_state.download_completed = True
                            else:
                                st.error("선택한 파일을 다운로드할 수 없습니다.")
            
        except Exception as e:
            st.error(f"오류가 발생했습니다: {str(e)}")
    
    # 다운로드 완료 메시지와 처음으로 버튼
    if st.session_state.download_completed:
        st.markdown("""
            <div class='success-message'>
                ✅ 다운로드가 완료되었습니다!
            </div>
        """, unsafe_allow_html=True)
        
        if st.button("처음으로 돌아가기", key="reset_button"):
            reset_app()
            st.experimental_rerun()

if __name__ == "__main__":
    main()
