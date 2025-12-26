"""マークダウンからPDF変換機能"""
import re
from fpdf import FPDF
from pathlib import Path


class MarkdownToPDF(FPDF):
    """マークダウンをPDFに変換するクラス"""
    
    def __init__(self, font_path: str = None):
        super().__init__()
        self.font_path = font_path or str(Path(__file__).parent / "fonts" / "NotoSansJP-Regular.ttf")
        self.set_auto_page_break(auto=True, margin=15)
        self.add_font("NotoSansJP", "", self.font_path, uni=True)
        self.set_font("NotoSansJP", "", 12)
        self.line_height = 6
    
    def add_markdown(self, markdown_text: str):
        """マークダウンテキストをPDFに追加"""
        lines = markdown_text.split("\n")
        i = 0
        
        while i < len(lines):
            line = lines[i].rstrip()
            
            # コードブロックの開始/終了行（```で始まる行）をスキップ
            if line.strip().startswith("```"):
                i += 1
                continue
            
            # 空行
            if not line:
                self.ln(5)
                i += 1
                continue
            
            # 見出し（# で始まる）
            if line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                heading_text = line.lstrip("# ").strip()
                self._add_heading(heading_text, level)
                i += 1
                continue
            
            # テーブル（| で始まる）
            if line.strip().startswith("|"):
                table_lines = [line]
                j = i + 1
                while j < len(lines) and lines[j].strip().startswith("|"):
                    table_lines.append(lines[j].rstrip())
                    j += 1
                self._add_table(table_lines)
                i = j
                continue
            
            # リスト（- または * で始まる）
            if line.strip().startswith("-") or line.strip().startswith("*"):
                list_text = re.sub(r"^[\s]*[-*]\s+", "", line).strip()
                self._add_list_item(list_text)
                i += 1
                continue
            
            # 通常のテキスト
            # 太字（**text**）や強調（*text*）を処理
            self._add_text_with_formatting(line)
            i += 1
    
    def _add_heading(self, text: str, level: int):
        """見出しを追加"""
        # マークダウン記号を除去
        text = re.sub(r"`([^`]+)`", r"\1", text)  # インラインコード
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # 太字
        text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)  # 強調
        
        sizes = {1: 20, 2: 18, 3: 16, 4: 14, 5: 13, 6: 12}
        size = sizes.get(level, 12)
        self.set_font("NotoSansJP", "", size)
        self.ln(8)
        self.cell(0, 10, text, ln=1)
        self.set_font("NotoSansJP", "", 12)
        self.ln(3)
    
    def _add_list_item(self, text: str):
        """リスト項目を追加"""
        # マークダウン記号を除去
        text = re.sub(r"`([^`]+)`", r"\1", text)  # インラインコード
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # 太字
        text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)  # 強調
        
        self.set_font("NotoSansJP", "", 11)
        # リストマーカーを追加
        x = self.get_x()
        y = self.get_y()
        self.cell(5, 5, "•", ln=0)
        self.set_x(x + 7)
        # テキストを追加（改行対応）
        self.multi_cell(0, 5, text, ln=1)
        self.set_font("NotoSansJP", "", 12)
    
    def _add_text_with_formatting(self, text: str):
        """フォーマット付きテキストを追加（太字など）"""
        # マークダウン記号を除去
        # インラインコード（`code`）を除去
        text = re.sub(r"`([^`]+)`", r"\1", text)
        # 太字（**text**）を除去
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        # 強調（*text*）を除去（太字の後に処理、**text**と区別するため）
        text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)
        
        self.set_font("NotoSansJP", "", 11)
        # 長いテキストは自動改行
        self.multi_cell(0, 5, text, ln=1)
        self.set_font("NotoSansJP", "", 12)
    
    def _add_table(self, table_lines: list):
        """テーブルを追加"""
        if len(table_lines) < 2:
            return
        
        # セルを分割
        def parse_row(row: str) -> list:
            cells = [cell.strip() for cell in row.split("|") if cell.strip()]
            return cells
        
        # セパレータ行かどうかを判定する関数
        def is_separator_row(row: str) -> bool:
            """行がセパレータ行（すべてのセルが `-` のみで構成）かどうかを判定"""
            cells = parse_row(row)
            if not cells:
                return False
            # すべてのセルが `-` のみで構成されているかチェック
            return all(re.match(r'^[\s\-:]+$', cell) for cell in cells)
        
        # ヘッダー行とセパレータ行をスキップ
        header = table_lines[0]
        if len(table_lines) > 1 and is_separator_row(table_lines[1]):
            data_rows = table_lines[2:]
        else:
            data_rows = table_lines[1:]
        
        header_cells = parse_row(header)
        if not header_cells:
            return
        
        # テーブル幅を計算
        col_width = (self.w - 2 * self.l_margin) / len(header_cells)
        
        self.ln(5)
        self.set_font("NotoSansJP", "", 10)
        
        # ヘッダー行
        x = self.get_x()
        y = self.get_y()
        for cell in header_cells:
            # マークダウン記号を除去
            cell_text = re.sub(r"`([^`]+)`", r"\1", cell)  # インラインコード
            cell_text = re.sub(r"\*\*([^*]+)\*\*", r"\1", cell_text)  # 太字
            cell_text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", cell_text)  # 強調
            self.cell(col_width, 7, cell_text, border=1, ln=0, align="C")
        self.ln()
        
        # データ行
        for row in data_rows:
            # セパレータ行が混入していないかチェック
            if is_separator_row(row):
                continue
            cells = parse_row(row)
            if len(cells) != len(header_cells):
                continue
            # すべてのセルが空の場合はスキップ
            if all(not cell.strip() for cell in cells):
                continue
            for cell in cells:
                # マークダウン記号を除去
                cell_text = re.sub(r"`([^`]+)`", r"\1", cell)  # インラインコード
                cell_text = re.sub(r"\*\*([^*]+)\*\*", r"\1", cell_text)  # 太字
                cell_text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", cell_text)  # 強調
                # セル内のテキストが長い場合は調整
                cell_text = cell_text[:30] + "..." if len(cell_text) > 30 else cell_text
                self.cell(col_width, 6, cell_text, border=1, ln=0, align="L")
            self.ln()
        
        self.set_font("NotoSansJP", "", 12)
        self.ln(5)


def markdown_to_pdf(markdown_text: str, output_path: str = None, font_path: str = None) -> bytes:
    """
    マークダウンテキストをPDFに変換
    
    Args:
        markdown_text: マークダウンテキスト
        output_path: 出力ファイルパス（Noneの場合はバイト列を返す）
        font_path: フォントファイルのパス
    
    Returns:
        PDFのバイト列（output_pathがNoneの場合）
    """
    pdf = MarkdownToPDF(font_path=font_path)
    pdf.add_page()
    pdf.add_markdown(markdown_text)
    
    if output_path:
        pdf.output(output_path)
        return None
    else:
        result = pdf.output(dest="S")
        # fpdf2のoutput(dest="S")は文字列またはバイト列を返す可能性がある
        if isinstance(result, str):
            return result.encode("latin-1")
        elif isinstance(result, bytearray):
            return bytes(result)
        else:
            return result

