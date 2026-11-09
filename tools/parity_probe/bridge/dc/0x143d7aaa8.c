
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

undefined4 FUN_143d7aaa8(undefined8 param_1,undefined8 param_2)

{
  int *piVar1;
  uint uVar2;
  ulonglong uVar3;
  char cVar4;
  int iVar5;
  undefined4 uVar6;
  longlong lVar7;
  longlong *plVar8;
  undefined8 uVar9;
  longlong *plVar10;
  longlong lVar11;
  longlong *plVar12;
  longlong unaff_RBP;
  undefined8 extraout_XMM0_Qa;
  undefined8 extraout_XMM0_Qa_00;
  undefined8 extraout_XMM0_Qa_01;
  undefined8 extraout_XMM0_Qa_02;
  undefined8 extraout_XMM0_Qa_03;
  undefined8 extraout_XMM0_Qa_04;
  undefined8 extraout_XMM0_Qa_05;
  undefined8 extraout_XMM0_Qa_06;
  undefined8 in_stack_00000040;
  undefined8 in_stack_00000048;
  longlong in_stack_00000050;
  undefined8 in_stack_00000058;
  undefined8 in_stack_00000060;
  undefined8 in_stack_00000068;
  undefined8 in_stack_00000070;
  undefined8 in_stack_00000078;
  undefined8 in_stack_00000080;
  undefined8 in_stack_00000088;
  undefined8 in_stack_00000090;
  undefined8 in_stack_00000098;
  undefined4 in_stack_000000a0;
  undefined8 in_stack_000000a8;
  undefined8 in_stack_000000b0;
  undefined *in_stack_000000e8;
  
  do {
    FUN_143a7c550(&UNK_1490f05e0,param_2);
    FUN_140001270(&DAT_14dba88a0);
    if (_DAT_14dba88a0 == -1) {
      in_stack_000000e8 = &UNK_148e0b6e1;
      _DAT_14dba8898 = FUN_142bc2b40(&UNK_148d88ba0,&UNK_1490f05d8,0xffffffff,0xff);
      FUN_140001350(&DAT_14dba88a0);
    }
    lVar11 = 0;
    lVar7 = lVar11;
    if (DAT_14dba87c8 == '\0') {
      lVar7 = _DAT_14dba8898;
    }
    in_stack_00000040 = 0;
    in_stack_00000048 = 0;
    in_stack_00000050 = 0;
    in_stack_00000058 = 0;
    in_stack_00000060 = _DAT_148a80860;
    in_stack_00000068 = _UNK_148a80868;
    in_stack_00000070 = 0;
    in_stack_00000078 = 0;
    in_stack_00000080 = 0;
    in_stack_00000088 = 0;
    in_stack_00000090 = 0;
    in_stack_00000098 = 0;
    in_stack_000000a0 = 0;
    in_stack_000000a8 = 0;
    in_stack_000000b0 = 0;
    if (lVar7 != 0) {
      FUN_142bc1e50(&stack0x00000040,0,0xffffffffffffffff,0,0);
    }
    lVar7 = FUN_143d82f90();
    plVar8 = (longlong *)FUN_1431499a0(extraout_XMM0_Qa,0xffffd8ed);
    uVar3 = plVar8[7];
    if (uVar3 != 0) {
      plVar10 = (longlong *)plVar8[1];
      if (0xf < (ulonglong)plVar10[3]) {
        plVar10 = (longlong *)*plVar10;
      }
      if (*(code **)(lVar7 + 0x38) != (code *)0x0) {
        uVar9 = (**(code **)(lVar7 + 0x38))
                          (*(undefined8 *)(lVar7 + 0x30),*(undefined8 *)(lVar7 + 0x20));
        *(undefined8 *)(lVar7 + 0x30) = uVar9;
        *(undefined8 *)(lVar7 + 0x38) = 0;
      }
      if ((*(ulonglong *)(lVar7 + 0x30) & uVar3) != uVar3) {
        FUN_142ab4c10(~*(ulonglong *)(lVar7 + 0x30) & uVar3,&UNK_148a74874,plVar10);
      }
    }
    if (DAT_14dba87c8 == '\0') {
      FUN_143d7feb0(*(undefined8 *)(plVar8[6] + 8),plVar8[1]);
    }
    iVar5 = FUN_143149af0();
    if ((iVar5 != 0) &&
       (plVar10 = (longlong *)FUN_143149a10(extraout_XMM0_Qa_00,1,_DAT_14dba87f0),
       plVar10 != (longlong *)0x0)) {
      plVar12 = (longlong *)0x0;
      if (plVar10[1] != 0) {
        LOCK();
        piVar1 = (int *)(plVar10[1] + 8);
        *piVar1 = *piVar1 + 1;
        UNLOCK();
        plVar12 = (longlong *)plVar10[1];
      }
      plVar10 = (longlong *)*plVar10;
      if ((plVar10 != (longlong *)0x0) &&
         (cVar4 = func_0x000142abb820(plVar8,plVar10), cVar4 != '\0')) {
        if ((char)plVar8[10] == '\0') {
          uVar9 = (**(code **)(*plVar10 + 0x68))(plVar10,lVar7);
        }
        else {
          uVar9 = (**(code **)(*plVar10 + 0x70))();
        }
        uVar9 = FUN_143d78ad0(uVar9,plVar10,plVar8);
        lVar7 = lVar11;
        if (unaff_RBP != 0) {
          lVar7 = func_0x0001409ed100();
          uVar9 = extraout_XMM0_Qa_01;
        }
        if (*(char *)(lVar7 + 0xa9) != '\0') {
          uVar9 = FUN_143d7a1b0(uVar9,plVar10,plVar8);
        }
        if (DAT_14dc2baf8 == '\0') {
          lVar7 = lVar11;
          if (unaff_RBP != 0) {
            lVar7 = func_0x0001409ed100();
            uVar9 = extraout_XMM0_Qa_03;
          }
          cVar4 = *(char *)(lVar7 + 0xaa);
        }
        else {
          cVar4 = FUN_147963030();
          uVar9 = extraout_XMM0_Qa_02;
        }
        if (cVar4 != '\0') {
          FUN_143d7b5f0(uVar9,plVar10,plVar8);
        }
        if ((int)plVar8[0x11] == 1) {
          uVar6 = (**(code **)(*plVar8 + 8))();
          uVar9 = extraout_XMM0_Qa_04;
        }
        else {
          uVar6 = (**(code **)(*plVar8 + 0x10))(plVar8,plVar10);
          uVar9 = extraout_XMM0_Qa_05;
        }
        if (DAT_14d5077b8 != '\0') {
          uVar2 = *(uint *)((longlong)plVar8 + 0x44);
          if (unaff_RBP != 0) {
            lVar11 = func_0x0001409ed100();
            uVar9 = extraout_XMM0_Qa_06;
          }
          if (*(longlong *)(lVar11 + 0xb0) != 0) {
            piVar1 = (int *)(*(longlong *)(lVar11 + 0xb0) + (ulonglong)uVar2 * 4);
            *piVar1 = *piVar1 + 1;
          }
        }
        func_0x000143d507c0(uVar9,plVar8,0);
        if (plVar12 != (longlong *)0x0) {
          LOCK();
          plVar8 = plVar12 + 1;
          lVar7 = *plVar8;
          *(int *)plVar8 = (int)*plVar8 + -1;
          UNLOCK();
          if ((int)lVar7 == 1) {
            (**(code **)*plVar12)(plVar12);
            LOCK();
            piVar1 = (int *)((longlong)plVar12 + 0xc);
            iVar5 = *piVar1;
            *piVar1 = *piVar1 + -1;
            UNLOCK();
            if (iVar5 == 1) {
              (**(code **)(*plVar12 + 8))(plVar12);
            }
          }
        }
        if (in_stack_00000050 != 0) {
          FUN_142bc3320(&stack0x00000040,0xffffffffffffffff);
        }
        return uVar6;
      }
    }
    param_2 = func_0x0001407c7020(plVar8[1]);
  } while( true );
}

