package com.allahpan.common.domain;

/** Web 请求日志实体，记录 HTTP 请求的详细信息 */
public class WebLog {
    private String method;      // HTTP 方法（GET/POST 等）
    private String url;        // 请求 URL
    private String ip;          // 客户端 IP
    private String className;   // Controller 类名
    private String methodName;  // 方法名
    private Object[] args;      // 请求参数
    private Object result;      // 响应结果
    private long spendTime;    // 耗时（毫秒）
    private String errorMessage; // 错误信息

    public String getMethod() { return method; }
    public void setMethod(String method) { this.method = method; }
    public String getUrl() { return url; }
    public void setUrl(String url) { this.url = url; }
    public String getIp() { return ip; }
    public void setIp(String ip) { this.ip = ip; }
    public String getClassName() { return className; }
    public void setClassName(String className) { this.className = className; }
    public String getMethodName() { return methodName; }
    public void setMethodName(String methodName) { this.methodName = methodName; }
    public Object[] getArgs() { return args; }
    public void setArgs(Object[] args) { this.args = args; }
    public Object getResult() { return result; }
    public void setResult(Object result) { this.result = result; }
    public long getSpendTime() { return spendTime; }
    public void setSpendTime(long spendTime) { this.spendTime = spendTime; }
    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }

    @Override
    public String toString() {
        StringBuilder sb = new StringBuilder();
        sb.append("\n========== 请求日志 ==========\n");
        sb.append("IP      : ").append(ip).append("\n");
        sb.append("URL     : ").append(method).append(" ").append(url).append("\n");
        sb.append("Class   : ").append(className).append(".").append(methodName).append("\n");
        if (errorMessage != null) {
            sb.append("Error   : ").append(errorMessage).append("\n");
        }
        sb.append("Time    : ").append(spendTime).append(" ms\n");
        sb.append("================================");
        return sb.toString();
    }
}
