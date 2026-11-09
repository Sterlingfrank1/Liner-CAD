"""油杯（简化体）：杆 Φ8 插入盖的油杯孔，杯体 Φ18 在盖顶之上。装配坐标：轴线沿 Z，位于 X=Y=0。"""

from build123d import Cylinder, Pos


def model(D=48, od=8, cd=18, ch=12, rd=10, rh=6, pd=3):
    """D 轴衬外径（杆底 = D/2，贴轴衬外圆顶）；od 杆径；cd×ch 杯体；rd×rh 杯口凹坑；pd 油道孔径。"""
    z0, z1 = D / 2, D / 2 + 8  # 杆：轴衬外圆顶 → 盖顶
    stem = Pos(0, 0, (z0 + z1) / 2) * Cylinder(od / 2, z1 - z0)
    cup = Pos(0, 0, z1 + ch / 2) * Cylinder(cd / 2, ch)
    body = stem + cup
    body = body - Pos(0, 0, z1 + ch - rh / 2) * Cylinder(rd / 2, rh + 0.01)
    return body - Pos(0, 0, (z0 + z1 + ch - rh) / 2) * Cylinder(pd / 2, z1 + ch - rh - z0 + 0.01)
