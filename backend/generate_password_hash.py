#!/usr/bin/env python3
import getpass
import sys

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def main() -> int:
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        password = getpass.getpass("请输入明文密码: ")

    if not password:
        print("密码不能为空", file=sys.stderr)
        return 1

    print(pwd_context.hash(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
