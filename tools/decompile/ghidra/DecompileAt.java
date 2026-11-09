// Decompile the functions at the given addresses (creating them if needed).
// args: OUTDIR ADDR [ADDR...]
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import java.io.*;

public class DecompileAt extends GhidraScript {
    public void run() throws Exception {
        String[] a = getScriptArgs();
        File out = new File(a[0]); out.mkdirs();
        DecompInterface d = new DecompInterface();
        d.openProgram(currentProgram);
        for (int i = 1; i < a.length; i++) {
            Address ad = toAddr(a[i]);
            Function f = getFunctionAt(ad);
            if (f == null) {
                new DisassembleCommand(ad, null, true).applyTo(currentProgram, monitor);
                new CreateFunctionCmd(ad).applyTo(currentProgram, monitor);
                f = getFunctionAt(ad);
            }
            if (f == null) { println("no function at " + a[i]); continue; }
            // disassemble the body's callees so calls resolve to names
            DecompileResults r = d.decompileFunction(f, 300, monitor);
            String c = r.decompileCompleted() ? r.getDecompiledFunction().getC() : ("FAILED: " + r.getErrorMessage());
            try (PrintWriter w = new PrintWriter(new File(out, a[i] + ".c"))) { w.print(c); }
            println("decompiled " + a[i] + " " + c.length());
        }
    }
}
