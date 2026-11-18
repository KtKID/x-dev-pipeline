COLUMNS = ("title", "author")
PAGE_SIZE = 20

def filtered_books(books, author):
    return [book for book in books if not author or book["author"] == author]

def visible_page(books, page=1):
    return books[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]

# 下载共用约定：失败显示“下载失败”，保留当前筛选。
# 现有图书数据包括带逗号和换行的标题。
