MODULE Module1
    CONST robtarget Target_10:=[[430.149444003,0,262.870109053],[0.50000002,0,0.866025392,0],[0,0,0,1],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget Target_20:=[[382.118748209,0,182.513936698],[0.499999994,0,0.866025407,0],[0,0,0,1],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget Target_30:=[[635.009450895,0,327.754464907],[0.50000002,0,0.866025392,0],[0,0,0,1],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget Target_10_4:=[[430.149444003,0,262.870109053],[0.50000002,0,0.866025392,0],[0,0,0,1],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];

    PROC main()
        WHILE TRUE DO

            ! Wait until a signal says an object is ready on the conveyor
            WaitUntil in_0=1;

            ! Call the pick and place function
            Path_10;

            ! Send a signal that the robot finished the task
            SetDO out_0,1;
            WaitTime 0.5;
            SetDO out_0,0;

            ! Wait until the start signal resets before next cycle
            WaitDI in_0,0;




        ENDWHILE
    ENDPROC

    PROC Path_10()
        ! Move down slowly to the exact position of the object
        MoveL Target_10,v1000,z100,tool0\WObj:=wobj0;
        MoveL Target_20,v1000,z100,tool0\WObj:=wobj0;

        ! Close the gripper to grab the object
        SetDO out_1,1;

        WaitTime 1;

        ! Move the robot above the box
        MoveL Target_30,v1000,z100,tool0\WObj:=wobj0;
        WaitTime 1;

        ! Open the gripper to release the object
        SetDO out_1,0;

        WaitTime 1;

        ! Move the robot back up to avoid hitting the box
        MoveL Target_10_4,v1000,z100,tool0\WObj:=wobj0;


    ENDPROC
ENDMODULE