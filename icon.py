from PIL import Image, ImageDraw


def create_icon():
    # 64x64 크기의 아이콘 생성
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # 배경 원 그리기
    draw.ellipse([4, 4, size - 4, size - 4], fill="#FF0000")

    # X 모양 그리기
    margin = 16
    draw.line([margin, margin, size - margin, size - margin], fill="white", width=4)
    draw.line([size - margin, margin, margin, size - margin], fill="white", width=4)

    # PNG 파일로 저장
    image.save("icon.png")


if __name__ == "__main__":
    create_icon()
