# XtQuant
迅投QMT接口相关介绍和常用功能封装

## xtquant介绍

`xtquant`是`QMT`官方内置的`XtMiniQmt`极简客户端对应的Python接口，目前支持的版本为3.6~3.8，可支持历史行情下载、实时数据订阅、外部数据访问、普通账户和两融账户交易(需开通相关权限)，对量化交易支持的比较完善。

`QMT`内置的Python版本为3.6，`XtMiniQmt.exe`存在于QMT安装目录下的`bin.x64`子目录中, `xtquant`库默认安装在`bin.x64\Lib\site-packages`中，因此，如果我们想在自定义的`Python`中调用，只需将`xtquant`拷贝到python安装目录的`Lib\site-packages`中便可。

`xtquant`主要包含两大块：
- **xtdata**：`xtdata`提供和`MiniQmt`的交互接口，本质是和`MiniQmt`建立连接，由`MiniQmt`处理行情数据请求，再把结果回传返回到`python`层。需要注意的是这个模块的使用目前并不需要登录，因此只要安装了`QMT`,就可以无门槛的使用其提供的数据服务。
- **xttrader**：`xttrader`是基于迅投`MiniQMT`衍生出来的一套完善的Python策略运行框架，对外以Python库的形式提供策略交易所需要的交易相关的API接口。该接口需开通A股实盘版权限方可使用。

在运行使用`XtQuant`的程序前需要先启动`MiniQMT`客户端。通常有两种方式，一种是直接启动极简QMT客户端`XtMiniQmt.exe`

![极简客户端](misc/XtMiniQmt.png)

如果登录时提示没有相关权限，可尝试启动QMT量化交易终端`XtItClient.exe`,在登录界面选择极简模式

![极简客户端](misc/XtItClient.png)

## 行情接口封装
