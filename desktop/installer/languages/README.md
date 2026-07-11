# 安装器语言文件

`ChineseSimplified.isl` 来自 Inno Setup 官方源码仓库 `jrsoftware/issrc` 的 `is-6_7_1` 标签：

```text
Files/Languages/Unofficial/ChineseSimplified.isl
```

保留上游文件内的维护者与翻译来源说明。构建脚本会将该文件转换为带 UTF-8 BOM 的临时副本，再交给 Inno Setup 6.7.1 编译，避免依赖构建机是否额外安装语言包。
