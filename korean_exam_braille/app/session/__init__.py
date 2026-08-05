"""UI 셸이 호출하는 Qt-free 세션 API.

도메인 포트·파이프라인을 조립해 창/위젯이 저수준 모듈을 직접 import하지 않게 한다.
"""

from korean_exam_braille.app.session.pdf_structure import PdfStructureService
from korean_exam_braille.app.session.workspace import ConversionWorkspace

__all__ = ["ConversionWorkspace", "PdfStructureService"]
