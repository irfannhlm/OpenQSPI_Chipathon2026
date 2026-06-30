/******************************************************************************************************************
*
*      FILE NAME       : W25QxxNExxIx_v1.0n.v
*      DESCRIPTION     : Verilg-HDL model of Winbond Electronics Corp. series Serial Flash Memory
*      VERSION         : Ver 1.0n
*      RELEASE         : JUL, 2025
*      PART NUMBER     : W25QxxNExxIx
*      MEMORY DENSITY  : xxMb
*      Max.SPEED       : N/A
*      AUTHOR          : Lydia CHAO
*
*                                                 Copyright(c)  Winbond Electronics Corp., 2025. All rights reserved.
*******************************************************************************************************************/

/*******************************************************************************
* Modification History
* ------------------------------------------------------------------------------
* Version     Author      Date     Notes
* ------------------------------------------------------------------------------
*  1.0n       Lydia     20250728   * Initial Version Release
*******************************************************************************/

`timescale 1ns / 100ps

module W25QxxNExxIx (CSn, CLK, DIO, DO, WPn, HOLDn, RESETn);
input CSn, CLK, RESETn;
inout DIO;
inout WPn;
inout HOLDn;
inout DO;

`define MEM_FILENAME    "MEM.TXT"                               
`define SECSI_FILENAME  "SECSI.TXT"                             
`define SFDP_FILENAME   "SFDP.TXT"                              
`define SREG_FILENAME   "SREG.TXT"                              

parameter NUM_SEC_PAGES = 3;					
parameter PAGESIZE  	= 256;
parameter SECTORSIZE 	= 4096;
parameter HALFBLOCKSIZE = 32768;
parameter BLOCKSIZE 	= 65536;
parameter MANUFACTURER 	= 8'hEF;
parameter UNIQUE_ID 	= 64'hFFFFFFFFFFFFFFFF;			


parameter	CE_5			=	5;
parameter	CE_10			=	10;
parameter	CE_20			=	20;
parameter	CE_40			=	40;


`ifdef	IM
    parameter	JEDEC_ID_HI		=	8'h85;
`elsif	IG
    parameter	JEDEC_ID_HI		=	8'h65;
`endif


`ifdef W25Q81NE
    parameter	NUM_BLOCKS		=	16;
    parameter	WIDTH_PA_ADDR		=	20;
    parameter	TABLE_SHIFT1		=	3'd0;//shift table(lower)
    parameter	TABLE_SHIFT2		=	3'd0;//shift table(upper)
    parameter	TABLE_UPPER_LIMIT	=	3'd4;
    parameter	DEVICE_ID		=	8'h13;
    parameter	JEDEC_ID_LO		=	8'h14;
    parameter	TCE_PAR			=	CE_5;
`elsif W25Q16NE
    parameter	NUM_BLOCKS		=	32;
    parameter	WIDTH_PA_ADDR		=	21;
    parameter   TABLE_SHIFT1            =       3'd0;//shift table(lower) 
    parameter   TABLE_SHIFT2            =       3'd0;//shift table(upper)
    parameter	TABLE_UPPER_LIMIT	=	3'd5;
    parameter	DEVICE_ID		=	8'h14;
    parameter	JEDEC_ID_LO		=	8'h15;
    parameter	TCE_PAR			=	CE_10;
`elsif W25Q32NE
    parameter	NUM_BLOCKS		=	64;
    parameter   TABLE_SHIFT1            =       3'd0;//shift table(lower)
    parameter   TABLE_SHIFT2            =       3'd0;//shift table(upper)
    parameter	WIDTH_PA_ADDR		=	22;
    parameter	TABLE_UPPER_LIMIT	=	3'd6;
    parameter	DEVICE_ID		=	8'h15;
    parameter	JEDEC_ID_LO		=	8'h16;
    parameter	TCE_PAR			=	CE_20;
`elsif W25Q65NE
    parameter	NUM_BLOCKS		=	128;
    parameter   TABLE_SHIFT1            =       3'd1;//shift table(lower)
    parameter   TABLE_SHIFT2            =       3'd1;//shift table(upper)
    parameter	WIDTH_PA_ADDR		=	23;
    parameter	TABLE_UPPER_LIMIT	=	3'd6;
    parameter	DEVICE_ID		=	8'h16;
    parameter	JEDEC_ID_LO		=	8'h17;
    parameter	TCE_PAR			=	CE_40;
`endif

parameter	NUM_PAGES		= BLOCKSIZE / PAGESIZE * NUM_BLOCKS;
parameter 	ADDRESS_MASK 		= (NUM_PAGES * PAGESIZE) - 1;		


reg [7:0] memory [0:(NUM_PAGES * PAGESIZE) - 1];	                      
reg [WIDTH_PA_ADDR - 1:0] protect_pa_lower; //protect range -Lydia 250715
reg [WIDTH_PA_ADDR - 1:0] protect_pa_upper; //protect range -Lydia 250715
reg [7:0] page_latch [0:PAGESIZE-1];                                       	
reg [7:0] secsi[0:(NUM_SEC_PAGES * (SECTORSIZE/PAGESIZE) * PAGESIZE) - 1]; 	
reg [7:0] sfdp[0:PAGESIZE-1];                                                	

reg [31:0] status_reg;				      				
reg [31:0] status_reg_shadow;							
reg status_reg_otp [31:0];      						
reg [23:0] byte_address;				    			
reg [23:0] prog_byte_address;   						
reg [8:0] prog_byte_number;							
reg [7:0] mode_reg;					        		
reg [7:0] wrap_reg;             						
reg [7:0] read_param_reg;        						
reg [7:0] read_param_reg_shadow; 						
reg [4:0] get_dummy_cyc; //new for dummy task -Lydia 250715
reg [4:0] get_dummy_cyc_dtr; //new for dummy task -Lydia 250715


reg flag_prog_page;         							
reg flag_prog_secsi_page;        						
reg flag_erase_sector;								
reg flag_erase_secsi_sector;
reg flag_erase_half_block;							
reg flag_erase_block;								
reg flag_erase_bulk;								
reg flag_power_up_exec;
reg flag_power_down;
reg flag_power_up_sig_read;
reg flag_write_status_reg;
reg flag_suspend;               						
reg flag_resume;                						
reg flag_suspend_enabled;       						
reg flag_slow_read_reg;
wire flag_slow_read = flag_slow_read_reg;
reg flag_volatile_sr_write;     						
reg flag_read_op_reg;
wire #1 flag_read_op = flag_read_op_reg;					
reg flag_qpi_mode;             							
reg flag_enable_reset;         							
reg flag_enable_otp;
reg flag_otp;
reg flag_reset;                							
reg flag_reset_condition;      							
reg flag_set_read_param;       							

reg timing_error;								

reg [7:0] in_byte;								
reg [7:0] out_byte;


reg WPn_Reg, WPn_Output_Enable_reg; 
wire WPn_Output_Enable = WPn_Output_Enable_reg;


reg HOLDn_Reg, HOLDn_Output_Enable; 


reg DO_Reg, DO_Output_Enable, temp_DO_Output_Enable;


reg DIO_Reg, DIO_Output_Enable_reg, temp_DIO_Output_Enable_reg;
wire DIO_Output_Enable = DIO_Output_Enable_reg;


reg HOLDn_Active;


reg [7:0]  cmd_byte;
reg [7:0]  null_reg;
reg [7:0]  temp;

integer  x;
integer	 fileno;
reg [15:0] file_sector;
reg [15:0] file_length;


`define CMD_WRITE_DISABLE 			      		8'h04 
`define CMD_WRITE_ENABLE  			      		8'h06 
`define CMD_READ_STATUS				        	8'h05 
`define CMD_WRITE_STATUS				       	8'h01 
`define CMD_READ_STATUS2				       	8'h35 
`define CMD_WRITE_STATUS2          				8'h31 
`define CMD_READ_STATUS3           				8'h15 
`define CMD_WRITE_STATUS3          				8'h11 
`define CMD_READ_DATA				          	8'h03 
`define CMD_READ_DATA_FAST			      		8'h0B 
`define CMD_READ_DATA_FAST_WRAP    				8'h0C 
`define CMD_READ_DATA_FAST_DUAL		  			8'h3B 
`define CMD_READ_DATA_FAST_DUAL_IO				8'hBB 
`define CMD_READ_DATA_FAST_QUAD		  			8'h6B 
`define CMD_READ_DATA_FAST_QUAD_IO				8'hEB 

`ifdef IM
    `define CMD_READ_DATA_FAST_DTR                              8'h0D
    `define CMD_READ_DATA_FAST_DTR_WRAP                         8'h0E
    `define CMD_READ_DATA_FAST_DUAL_IO_DTR                      8'hBD
    `define CMD_READ_DATA_FAST_QUAD_IO_DTR                      8'hED
`endif


`define CMD_PAGE_PROGRAM				       	8'h02 
`define CMD_PAGE_PROGRAM_QUAD			   		8'h32 
`define CMD_BLOCK_ERASE				        	8'hD8 
`define CMD_HALF_BLOCK_ERASE			    		8'h52 
`define CMD_SECTOR_ERASE				       	8'h20 
`define CMD_BULK_ERASE				         	8'hC7 
`define CMD_BULK_ERASE2				        	8'h60 
`define CMD_DEEP_POWERDOWN			      		8'hB9 
`define CMD_READ_SIGNATURE			      		8'hAB 
`define CMD_READ_ID					        8'h90 
`define CMD_READ_ID_DUAL           				8'h92 
`define CMD_READ_ID_QUAD           				8'h94 
`define CMD_READ_JEDEC_ID			       		8'h9F 
`define CMD_READ_UNIQUE_ID			      		8'h4B 
`define CMD_SUSPEND                				8'h75 
`define CMD_RESUME                 				8'h7A 
`define CMD_SET_BURST_WRAP         				8'h77 
`define CMD_MODE_RESET             				8'hFF 
`define CMD_DISABLE_QPI            				8'hFF 
`define CMD_ENABLE_QPI             				8'h38 
`define CMD_ENABLE_RESET           				8'h66 
`define CMD_CHIP_RESET             				8'h99 
`define CMD_SET_READ_PARAM         				8'hC0 
`define CMD_SREG_PROGRAM           				8'h42 
`define CMD_SREG_ERASE             				8'h44 
`define CMD_SREG_READ              				8'h48 
`define CMD_WRITE_ENABLE_VSR       				8'h50 
`define CMD_READ_SFDP              				8'h5A 


`define CMD_ENABLE_OTP                                          8'hAA
`define CMD_SR_OTP                                              8'h55



`define STATUS_S23	   	24'h800000
`define STATUS_DRV1      	24'h400000
`define STATUS_DRV0      	24'h200000
`define STATUS_CL		24'h100000
`define STATUS_SUS       	24'h008000
`define STATUS_CMP       	24'h004000
`define STATUS_LB3       	24'h002000
`define STATUS_LB2       	24'h001000
`define STATUS_LB1       	24'h000800
`define STATUS_S10		24'h000400
`define STATUS_QE		24'h000200
`define STATUS_SRL		24'h000100
`define STATUS_SRP		24'h000080
`define STATUS_SEC		24'h000040
`define STATUS_TB 		24'h000020
`define STATUS_BP2		24'h000010
`define STATUS_BP1		24'h000008
`define STATUS_BP0	   	24'h000004
`define STATUS_WEL		24'h000002
`define STATUS_WIP	 	24'h000001

`define S23	 	23
`define DRV1 		22
`define DRV0 		21
`define CL		20
`define S19		19
`define S18  		18
`define S17  		17
`define S16  		16
`define SUS  		15
`define CMPB 		14
`define LB3  		13
`define LB2  		12
`define LB1  		11
`define S10         	10
`define QE	  	9
`define SRL		8
`define SRP		7
`define SEC		6
`define TB 	 	5
`define BP2	 	4
`define BP1	 	3
`define BP0	 	2
`define WEL	 	1
`define WIP	 	0



wire flag_quad_mode = status_reg[`QE];
wire flag_quad_mode_cs = !flag_quad_mode & !CSn;

wire [2:0]	sr_BP	= status_reg[`BP2:`BP0]; //Lydia  250714

specify

specparam tReset_Suspend_Max = 1000;      
                                          


specparam tSLCH = 10;					
specparam tCHSL = 10;					

specparam tSHSL_R = 10;					
specparam tSHSL_W = 50;

specparam tCHSH = 5;
specparam tSHCH = 5;

specparam tDVCH = 2;                      
specparam tCHDX = 5;                      

specparam tWHSL = 20;
specparam tSHWL = 100;

specparam tHLQZ = 12;
specparam tHHQX = 7;
specparam tSUS = 20000;

specparam tCHHL = 5;
specparam tHLCH = 5; 
specparam tCHHH = 5;
specparam tHHCH = 5;



$setup(negedge CSn, posedge CLK, tSLCH, timing_error);
$setup(posedge CLK, negedge CSn, tCHSL, timing_error);
$width(posedge CSn &&& flag_read_op, tSHSL_R, 0, timing_error);
$width(posedge CSn &&& (~flag_read_op), tSHSL_W, 0, timing_error);
$setup(posedge CLK, posedge CSn, tCHSH, timing_error);
$setup(posedge CSn, posedge CLK, tSHCH, timing_error);
$setup(posedge CLK, negedge HOLDn &&& (flag_quad_mode_cs),tCHHL, timing_error);
$hold(posedge CLK, negedge HOLDn &&& (flag_quad_mode_cs),tHLCH, timing_error);
$setup(posedge CLK, posedge HOLDn &&& (flag_quad_mode_cs),tCHHH, timing_error);
$hold(posedge CLK, posedge HOLDn &&& (flag_quad_mode_cs), tHHCH, timing_error);



specparam	tCLH  = 4;			
specparam 	tCLL  = 4;		        

$width(posedge CLK &&& (~flag_slow_read), tCLH, 0, timing_error);
$width(negedge CLK &&& (~flag_slow_read), tCLL, 0, timing_error);

specparam	tCRLH  = 8;			
specparam 	tCRLL  = 8;		        

$width(posedge CLK &&& (flag_slow_read), tCRLH, 0, timing_error);
$width(negedge CLK &&& (flag_slow_read), tCRLL, 0, timing_error);



$setup(DIO, posedge CLK &&& (~DIO_Output_Enable), tDVCH, timing_error);
$hold(posedge CLK, DIO &&& (~DIO_Output_Enable), tCHDX, timing_error);

endspecify


parameter 	tCLQV =  7;	
parameter	tSHQZ =  7;	
parameter	tW    =  2000000;		
parameter 	tRES1 =  20000;			
parameter	tDP   =  3000;			
parameter	tPP   =  600000;		
parameter	tSE   =  100000000;		
parameter 	tBE1  =  150000000;		
parameter 	tBE2  =  200000000;		
parameter     	tCE_unit =  1000000000;	//Lydia 250709	
parameter     tRESET  =  1000;                  


initial
begin :initialization

   

  integer x;
    	for(x = 0; x < (NUM_PAGES * PAGESIZE); x=x+1)
    		memory[x] = 8'hFF;

		
  $readmemh(`SECSI_FILENAME,secsi);
  $readmemh(`SFDP_FILENAME,sfdp);
  $readmemh(`SREG_FILENAME,status_reg_otp);


  chip_reset;

end


assign DIO = DIO_Output_Enable_reg ? DIO_Reg : 1'bz;
assign DO = DO_Output_Enable ? DO_Reg : 1'bz;
assign WPn = WPn_Output_Enable_reg ? WPn_Reg : 1'bz;
assign HOLDn = HOLDn_Output_Enable ? HOLDn_Reg : 1'bz;

always@(negedge RESETn)
  begin
    #tRESET;
    if(RESETn == 1'b0)
      begin
        flag_reset = 1;
        chip_reset;
      end
    else
      flag_reset = flag_reset;
  end

always@(negedge CSn)				
begin :read_opcode

  flag_read_op_reg = 1'b1;   			

	mode_reg = mode_reg & 8'hf0;

	if((mode_reg & 8'h30) != 8'h20)		
	   input_byte(cmd_byte);	        
		   
	if(!is_qpi(cmd_byte))
	begin
		$display("WARNING: Non-QPI command was executed in QPI mode");
    		$stop;
	end
	
	if(cmd_byte != `CMD_CHIP_RESET)
	   flag_enable_reset = 0;   	

	if(cmd_byte != `CMD_WRITE_ENABLE && cmd_byte != `CMD_WRITE_STATUS2) //clear flag_otp if not 06h or 31h  Lydia 250710
	    flag_otp = 0;	    

	$display("\nCommand = %h", cmd_byte);



	case (cmd_byte)				


   `CMD_SET_READ_PARAM :
    begin
      if(!status_reg[`WIP] && !flag_power_down) 
      begin
 		   		input_byte(read_param_reg_shadow);
     				flag_set_read_param = 1;
     				get_posclk_holdn;
     				flag_set_read_param = 0;
 		  end
    end  

    `CMD_ENABLE_QPI :
    begin
      if(!status_reg[`WIP] && !flag_power_down)
      begin
         if(status_reg[`QE] == 1)
             flag_qpi_mode = 1;
      end
    end  

      
    `CMD_MODE_RESET :
	  begin
	    if(!flag_power_down)   
 		       flag_qpi_mode = 0;
	  end
	
	  `CMD_ENABLE_RESET :            
	  begin
       flag_enable_reset = 1;		    
	  end
	    
	`CMD_CHIP_RESET :
	begin
		if(flag_enable_reset == 1)
		begin
    		flag_reset = 1;
			@(posedge CLK);
				flag_reset = 0;
       end
    end

 

		`CMD_DEEP_POWERDOWN :
		begin
      if(!status_reg[`WIP] && !flag_power_down)
      begin
		     flag_power_down = 1;
  				 @(posedge CLK);
		     flag_power_down = 0;
			end
		end
		
	  		
    

		`CMD_READ_SIGNATURE :
		begin
         if(!status_reg[`WIP])
         begin
           		flag_power_up_exec = 1;
           		input_byte(null_reg);
           		input_byte(null_reg);
           		input_byte(null_reg);
            	forever
           		begin
           		   output_byte(DEVICE_ID);
          			   flag_power_up_sig_read = 1;
           		end
         end
		end

		`CMD_READ_JEDEC_ID :
		begin
         if(!status_reg[`WIP] && !flag_power_down)
         begin
				    output_byte(MANUFACTURER);
			            output_byte(JEDEC_ID_HI);
				    output_byte(JEDEC_ID_LO);
         end
		end

		`CMD_READ_ID :
		begin
         if(!status_reg[`WIP] && !flag_power_down)
         begin
            byte_address = 0;               
            input_byte(byte_address[23:16]);
            input_byte(byte_address[15:8]);
            input_byte(byte_address[7:0]);
            forever
            begin
               if(byte_address[0])
	            begin
	               output_byte(DEVICE_ID);
                 output_byte(MANUFACTURER);
              end
              else
              begin
                 output_byte(MANUFACTURER);
                 output_byte(DEVICE_ID);
              end
            end				    
         end
      end

     `CMD_READ_ID_DUAL :  
	   begin
         if(!status_reg[`WIP] && !flag_power_down)
         begin
            byte_address = 0;                          
            input_byte_dual(byte_address[23:16]);
            input_byte_dual(byte_address[15:8]);
            input_byte_dual(byte_address[7:0]);
            input_byte_dual(mode_reg[7:0]);
            forever
            begin
               if(byte_address[0])
	            begin
	               output_byte_dual(DEVICE_ID);
                 output_byte_dual(MANUFACTURER);
               end
               else
               begin
                  output_byte_dual(MANUFACTURER);
                  output_byte_dual(DEVICE_ID);
               end
            end				    
         end
      end

      `CMD_READ_ID_QUAD :
      begin
         if(!status_reg[`WIP] && !flag_power_down && status_reg[`QE])
         begin  
            byte_address = 0;                       
            input_byte_quad(byte_address[23:16]);
            input_byte_quad(byte_address[15:8]);
            input_byte_quad(byte_address[7:0]);
            input_byte_quad(mode_reg[7:0]);                
            input_byte_quad(temp[7:0]);
            input_byte_quad(temp[7:0]);
            forever
            begin
               if(byte_address[0])
	            begin
	               output_byte_quad(DEVICE_ID);
                 output_byte_quad(MANUFACTURER);
               end
               else
               begin
                  output_byte_quad(MANUFACTURER);
                  output_byte_quad(DEVICE_ID);
               end
            end				    
         end
      end
    
   	`CMD_READ_UNIQUE_ID :
		begin
			if(!status_reg[`WIP] && !flag_power_down)
			begin
				input_byte(null_reg);
				input_byte(null_reg);
				input_byte(null_reg);
				input_byte(null_reg);
				output_byte(UNIQUE_ID[63:56]);
				output_byte(UNIQUE_ID[55:48]);
				output_byte(UNIQUE_ID[47:40]);
				output_byte(UNIQUE_ID[39:32]);	
				output_byte(UNIQUE_ID[31:24]);
				output_byte(UNIQUE_ID[23:16]);
				output_byte(UNIQUE_ID[15:8]);
				output_byte(UNIQUE_ID[7:0]);
			end
		end

			



		`CMD_WRITE_ENABLE :
		begin
			if((!flag_power_down)	&& (WPn || status_reg[`QE]))
				status_reg[`WEL] = 1;
	   end
	   
	   `CMD_WRITE_ENABLE_VSR :
	   begin
			if(!flag_power_down)	
			   flag_volatile_sr_write = 1;
	   end
	   
	   `CMD_WRITE_DISABLE :
	   begin
	      if(!flag_power_down)
				status_reg[`WEL] = 0;
	   end

		`CMD_READ_STATUS :
		begin
			 if(!flag_power_down)
			 begin
				 forever
				 begin
					  output_byte(status_reg[7:0]);
				 end
			 end
		end

		`CMD_READ_STATUS2 :
		begin
			if(!flag_power_down)
			begin
				forever
				begin
					output_byte(status_reg[15:8]);
				end
			end
		end

		`CMD_READ_STATUS3 :
		begin
			if(!flag_power_down)
			begin
				forever
				begin
					output_byte(status_reg[23:16]);
				end
			end
		end


		`CMD_WRITE_STATUS :
		begin
		    if(!status_reg[`WIP] && (status_reg[`WEL] || flag_volatile_sr_write) && !flag_power_down && !status_reg[`SUS])
		    begin
			flag_read_op_reg = 1'b0;
			
			case ({status_reg[`SRL],status_reg[`SRP]})
			    2'b00, 2'b01 :
			    begin
				if((status_reg[`SRP] && WPn) || !status_reg[`SRP] || flag_qpi_mode) 
				begin
				    status_reg_shadow[23:8] = status_reg[23:8];
				    input_byte(status_reg_shadow[7:0]);
				    flag_write_status_reg = 1;
           		       
				    if(flag_qpi_mode == 1)
					@(posedge CLK);
				    else
					get_posclk_holdn;    
				    flag_write_status_reg = 0;
				end
			    end
  			endcase
 		    end
		end
		
		`CMD_WRITE_STATUS2 :
		begin
		    if(!status_reg[`WIP] && (status_reg[`WEL] || flag_volatile_sr_write) 
			&& !flag_power_down && !status_reg[`SUS])
		    begin
			flag_read_op_reg = 1'b0;
			case ({status_reg[`SRL],status_reg[`SRP]})
			    2'b00, 2'b01 :
			    begin
				if((status_reg[`SRP] && WPn) || !status_reg[`SRP] || flag_qpi_mode) 
				begin
				    status_reg_shadow[23:16] = status_reg[23:16];
				    status_reg_shadow[7:0] = status_reg[7:0];
				    input_byte(status_reg_shadow[15:8]);			    
				    flag_write_status_reg = 1;
							    
				    if(flag_qpi_mode == 1)
					@(posedge CLK);
				    else
					get_posclk_holdn;   
				
				    flag_write_status_reg = 0;
				end
			    end
			endcase
		    end
		end

		`CMD_WRITE_STATUS3 :
		begin
	     	if(!status_reg[`WIP] && (status_reg[`WEL] || flag_volatile_sr_write) && !flag_power_down && !status_reg[`SUS])
        begin
            flag_read_op_reg = 1'b0;
				    case ({status_reg[`SRL],status_reg[`SRP]})
					  2'b00, 2'b01 :
					  begin
						   if((status_reg[`SRP] && WPn) || !status_reg[`SRP] || flag_qpi_mode) 
						   begin
							    status_reg_shadow[15:0] = status_reg[15:0];
			 				    input_byte(status_reg_shadow[23:16]);
							    
                  
							    flag_write_status_reg = 1;
							    
							    if(flag_qpi_mode == 1)
							       @(posedge CLK);
							    else
                     get_posclk_holdn;   
                  flag_write_status_reg = 0;
						   end
 					 end
				   endcase
		   end
		end




		`CMD_PAGE_PROGRAM :
		begin
			if(status_reg[`WEL] && !status_reg[`SUS] && !flag_power_down)
			begin
			   flag_read_op_reg = 1'b0;
				 write_page(0,0);
			end
		end

		`CMD_PAGE_PROGRAM_QUAD :
		begin
			if(status_reg[`WEL]&& !status_reg[`SUS] && status_reg[`QE] && !flag_power_down)
			begin
			   flag_read_op_reg = 1'b0;
	    			write_page(1,0);
			end
		end


      `CMD_SUSPEND :
      begin
         if(!flag_power_down && !flag_erase_bulk)
         begin
            if((!flag_suspend) && (flag_erase_sector || flag_erase_secsi_sector || flag_erase_half_block || flag_erase_block || flag_prog_page || flag_prog_secsi_page))
            begin
                flag_suspend = 1'b1;
                get_posclk_holdn;   
                flag_suspend = 1'b0;
            end
         end
      end
      
      `CMD_RESUME :
      begin
          if(!flag_power_down)
          begin
             if(flag_suspend)
             begin
                 flag_resume = 1'b1;
                 get_posclk_holdn;   
                 flag_resume = 1'b0;
             end
          end
      end
      
 
      
		`CMD_SECTOR_ERASE :
		begin
			if(status_reg[`WEL] && !flag_power_down && !status_reg[`SUS])
			begin
   		   flag_read_op_reg = 1'b0;

				input_byte(byte_address[23:16]);
				input_byte(byte_address[15:8]);
				input_byte(byte_address[7:0]);
				byte_address = byte_address & ADDRESS_MASK;
				if(!write_protected(byte_address))
				begin
					flag_erase_sector = 1;
					get_posclk_holdn;				
					flag_erase_sector = 0;
				end
			end
		end


		`CMD_HALF_BLOCK_ERASE :
		begin
			if(status_reg[`WEL] && !flag_power_down && !status_reg[`SUS])
			begin
			    flag_read_op_reg = 1'b0;

			    input_byte(byte_address[23:16]);
			    input_byte(byte_address[15:8]);
			    input_byte(byte_address[7:0]);
			    byte_address = byte_address & ADDRESS_MASK;
			    if(!write_protected(byte_address))
			    begin
				flag_erase_half_block = 1;
				get_posclk_holdn;				
				flag_erase_half_block = 0;
			    end
			end
		end

		`CMD_BLOCK_ERASE :
		begin
			if(status_reg[`WEL] && !flag_power_down && !status_reg[`SUS])
			begin
   		   flag_read_op_reg = 1'b0;

				input_byte(byte_address[23:16]);
				input_byte(byte_address[15:8]);
				input_byte(byte_address[7:0]);
				byte_address = byte_address & ADDRESS_MASK;
				if(!write_protected(byte_address))
				begin
					flag_erase_block = 1;
					get_posclk_holdn;				
					flag_erase_block = 0;
				end
			end
		end


		`CMD_BULK_ERASE, `CMD_BULK_ERASE2 :
		begin
			if(status_reg[`WEL] && !flag_power_down && !status_reg[`SUS])
			begin
			   flag_read_op_reg = 1'b0;
				case ({status_reg[`BP0],status_reg[`BP1]})
					2'b00 :
					begin
						flag_erase_bulk = 1;
						get_posclk_holdn;
						flag_erase_bulk = 0;
					end
				endcase
			end
		end



		`CMD_READ_DATA :
		begin
			if(!status_reg[`WIP] && !flag_power_down)
			begin
				flag_slow_read_reg = 1'b1;				
				input_byte(byte_address[23:16]);	
				input_byte(byte_address[15:8]);
				input_byte(byte_address[7:0]);
		 	forever
		 	begin
			  	byte_address = byte_address & ADDRESS_MASK;
                                output_byte(memory[byte_address]);
				byte_address = byte_address + 1;
			end
			end
		end
		


		`CMD_READ_DATA_FAST :
		begin
			if(!flag_power_down)
				read_page(1,0,0);
		end
		

		`ifdef IM

		`CMD_READ_DATA_FAST_DTR :
		begin
		    if(!status_reg[`WIP] && !flag_power_down && !flag_qpi_mode)
		    begin
			input_byte_DTR(byte_address[23:16]);	
	    		input_byte_DTR(byte_address[15:8]);
		    	input_byte_DTR(byte_address[7:0]);
             
	         	for(x = 5; x >= 0; x=x-1)
	         	begin
			    get_posclk_holdn;
			    null_reg[x] = DIO;
	         	end
   	      	
	         	forever
	         	begin
			    byte_address = byte_address & ADDRESS_MASK;
			    output_byte_DTR(memory[byte_address]);
	      		    byte_address = byte_address + 1;
	         	end
		    end
            
		    else if(!status_reg[`WIP] && !flag_power_down && flag_qpi_mode)
		    begin
			input_byte_quad_DTR(byte_address[23:16]);	
			input_byte_quad_DTR(byte_address[15:8]);
			input_byte_quad_DTR(byte_address[7:0]);
			byte_address = byte_address & ADDRESS_MASK;

			input_dummy(get_dummy_cyc_dtr); //new dummy task -Lydia 250716
			
			forever
			begin  //remove wrap function buz 0Dh no wrap  -Lydia 250710
			    byte_address = byte_address & ADDRESS_MASK;
			    output_byte_quad_DTR(memory[byte_address]);
			    byte_address = byte_address + 1;
			end
		    end        
		end

		`CMD_READ_DATA_FAST_DUAL_IO_DTR :
		begin
			if(!status_reg[`WIP] && !flag_power_down)
			begin
			
    
			input_byte_dual_DTR(byte_address[23:16]);	
			input_byte_dual_DTR(byte_address[15:8]);
			input_byte_dual_DTR(byte_address[7:0]);
			input_byte_dual_DTR(mode_reg[7:0]);

	   		for(x = 3; x >= 0; x=x-1)
	   		begin
	      			get_posclk_holdn;
         			null_reg[x] = DIO;
	   		end
   		
			forever
			begin
			  	byte_address = byte_address & ADDRESS_MASK;
				output_byte_dual_DTR(memory[byte_address]);
				byte_address = byte_address + 1;
			end
			end
		end

		`CMD_READ_DATA_FAST_QUAD_IO_DTR :
		begin
		    if(!status_reg[`WIP] && !flag_power_down && status_reg[`QE])
		    begin	
			input_byte_quad_DTR(byte_address[23:16]);	
			input_byte_quad_DTR(byte_address[15:8]);
			input_byte_quad_DTR(byte_address[7:0]);
			input_byte_quad_DTR(mode_reg[7:0]);

			input_dummy(get_dummy_cyc_dtr-1); //-1 for mode_reg use 1 CLK new dummy task -Lydia 250716 
		    end

		    forever
		    begin //remove wrap function buz EDh no wrap -Lydia 250710
			byte_address = byte_address & ADDRESS_MASK;
			output_byte_quad_DTR(memory[byte_address]);
			byte_address = byte_address + 1;
		    end
		end

		`CMD_READ_DATA_FAST_DTR_WRAP :
		begin
		    if(!status_reg[`WIP] && !flag_power_down && flag_qpi_mode)  //add QPI mode only   Lydia 250711
		    begin
			input_byte_quad_DTR(byte_address[23:16]);	
			input_byte_quad_DTR(byte_address[15:8]);
			input_byte_quad_DTR(byte_address[7:0]);
                          
			input_dummy(get_dummy_cyc_dtr); //new dummy task -Lydia 250716

			forever
			begin
			    byte_address = byte_address & ADDRESS_MASK;
			    output_byte_quad_DTR(memory[byte_address]);
            		    case ({read_param_reg[1],read_param_reg[0]})		    
				2'b00 :
				    byte_address[2:0]  = byte_address[2:0] + 1;
               			2'b01 :
				    byte_address[3:0] = byte_address[3:0] + 1;
               			2'b10 :
				    byte_address[4:0] = byte_address[4:0] + 1;
               			2'b11 :
                  		    byte_address[5:0] = byte_address[5:0] + 1;
            		    endcase
			end
                    end
		end
	    `endif

		`CMD_READ_DATA_FAST_WRAP :
		begin
		    if(!flag_power_down)
		    begin  
			if(flag_qpi_mode)
			    read_page_quadio(cmd_byte,0);     	       
			//else //should not use out of QPI mode -Lydia 250715 
			   // read_page(1,0,1);
		    end 
		end
		    
		`CMD_READ_DATA_FAST_DUAL :
		begin
			if(!flag_power_down)
				read_page(2,0,0);
		end
		

		`CMD_READ_DATA_FAST_QUAD :
		begin
			if(!flag_power_down && status_reg[`QE])
				read_page(3,0,0);
		end
		
		
		`CMD_READ_DATA_FAST_DUAL_IO :
		begin
			if(!flag_power_down)
				read_page_dualio(0);
		end
		

		`CMD_READ_DATA_FAST_QUAD_IO :
		begin
			if(!flag_power_down && status_reg[`QE])
				read_page_quadio(cmd_byte,0);
		end


		`CMD_SET_BURST_WRAP :
		begin
		    if(!status_reg[`WIP] && !flag_power_down && status_reg[`QE])
		    begin
			input_byte_quad(temp[7:0]);	
			input_byte_quad(temp[7:0]);	
			input_byte_quad(temp[7:0]);	   	    	      	    	   
			input_byte_quad(wrap_reg[7:0]);	   	    	      	    	   
		    end
		end
		
		`CMD_READ_SFDP :
		begin
			if(!flag_power_down)
			begin
				flag_slow_read_reg = 1'b1;
				read_page(0,2,0);
			end
		end
		
		


      `CMD_SREG_READ :
      begin
      			if(!flag_power_down)
			   begin
				    read_page(0,1,0);
			   end
		  end
      
      `CMD_SREG_ERASE :
      begin
			if(status_reg[`WEL] && !flag_power_down && !status_reg[`SUS])
			begin
			   flag_read_op_reg = 1'b0;
			   
				 input_byte(byte_address[23:16]);
				 input_byte(byte_address[15:8]);
				 input_byte(byte_address[7:0]);
				 byte_address = byte_address & ADDRESS_MASK;
				 case (byte_address[23:8])
					16'h10 :
					begin
					   if(!status_reg[`LB1])
					   begin
      						   flag_erase_secsi_sector = 1;
						   get_posclk_holdn;
						   flag_erase_secsi_sector = 0;
						end
					end
					16'h20 :
					begin
					   if(!status_reg[`LB2])
					   begin
      						   flag_erase_secsi_sector = 1;
						   get_posclk_holdn;
						   flag_erase_secsi_sector = 0;
						end
					end
					16'h30 :
					begin
					   if(!status_reg[`LB3])
					   begin
      						   flag_erase_secsi_sector = 1;
						   get_posclk_holdn;
						   flag_erase_secsi_sector = 0;
						end
					end
		
				endcase
			end
      end
      
    `CMD_SREG_PROGRAM :
		begin
			if(status_reg[`WEL] && !flag_power_down && !status_reg[`SUS])
			begin
			   flag_read_op_reg = 1'b0;
            begin
               if(!status_reg[`WIP])
               begin

            		    input_byte(prog_byte_address[23:16]);
		              input_byte(prog_byte_address[15:8]);
		              input_byte(prog_byte_address[7:0]);
			      prog_byte_address = prog_byte_address & ADDRESS_MASK; //add ADDRESS_MASK -Lydia 250710
		            
   				          case (prog_byte_address[23:8])
					         16'h10 :
					         if(!status_reg[`LB1])
					            fill_page_latch(0,prog_byte_address,1);
  				                 16'h20 :
					         if(!status_reg[`LB2])
					            fill_page_latch(0,prog_byte_address,1);
					         16'h30 :
					         if(!status_reg[`LB3])
					            fill_page_latch(0,prog_byte_address,1);
				          endcase
		          end
	         end
         end
		end


    
    
        `CMD_ENABLE_OTP :                                                         
          begin
                   flag_enable_otp = 1;		    
          end
            
        `CMD_SR_OTP :
          begin
               if(flag_enable_otp == 1)
                  flag_otp = 1;
              end
		
		default :
		begin
			$display("Invalid Opcode. (%0h)",cmd_byte);
                        $stop;
		end
	endcase
end



always @(posedge CSn)		   		      
begin :disable_interface
	#tSHQZ;						                  
	HOLDn_Active = 1'b0;           
	DO_Output_Enable = 1'b0;			    
	DIO_Output_Enable_reg = 1'b0;		
	WPn_Output_Enable_reg = 1'b0;		
	HOLDn_Output_Enable = 1'b0;		  
	flag_slow_read_reg = 1'b0;			  

	disable input_byte;
	disable input_byte_dual;
	disable input_mode_dual;
	disable input_byte_quad;
	disable output_byte;
	disable output_byte_dual;
	disable output_byte_quad;
	disable read_opcode;
	disable write_page;
	disable fill_page_latch;
	disable read_page;
	disable read_page_dualio;
	disable read_page_quadio;
	disable get_posclk_holdn;
	disable get_negclk_holdn;
	disable input_dummy; //task wait dummy cycle -Lydia 250715
end



always @(negedge (HOLDn & !status_reg[`QE] & !CSn))		   		      
begin

   if(!HOLDn)
   begin
      #tHLQZ;
      temp_DIO_Output_Enable_reg = DIO_Output_Enable_reg;
      temp_DO_Output_Enable = DO_Output_Enable;
      DIO_Output_Enable_reg = 1'b0;               
      DO_Output_Enable = 1'b0;
      HOLDn_Active = 1'b1;
   end
   
   
end


always @(posedge HOLDn)		   		      
begin

   if(HOLDn_Active == 1'b1)
   begin
       #tHHQX;
       DIO_Output_Enable_reg = temp_DIO_Output_Enable_reg;
       DO_Output_Enable = temp_DO_Output_Enable;	
       HOLDn_Active = 1'b0;
   end
   
end



task chip_reset;
integer x;
begin

	
	temp_DIO_Output_Enable_reg = 1'b0;
	DIO_Output_Enable_reg = 1'b0;				
	temp_DO_Output_Enable = 1'b0;
	DO_Output_Enable = 1'b0;	   				 
	WPn_Output_Enable_reg = 1'b0;				
	HOLDn_Output_Enable = 1'b0;				  
	HOLDn_Active = 1'b0;

	
	
	DIO_Reg = 1'b0;
	DO_Reg = 1'b0;
	WPn_Reg = 1'b0;
	HOLDn_Reg = 1'b0;
	
	mode_reg = 8'h00;					        
	wrap_reg = 8'b00010000;       
	read_param_reg = 8'h00;       

   
	status_reg = 0;             	
`ifdef IM
    status_reg[`QE] = status_reg_otp[`QE]; 
`elsif IG
    status_reg[`QE] = 1'b1; 
`endif

  status_reg[`SRL] = status_reg_otp[`SRL];
  status_reg[`SRP] = status_reg_otp[`SRP];
  status_reg[`BP0] = status_reg_otp[`BP0];
  status_reg[`BP1] = status_reg_otp[`BP1];
  status_reg[`BP2] = status_reg_otp[`BP2];
  status_reg[`TB] = status_reg_otp[`TB];
  status_reg[`CMPB] = status_reg_otp[`CMPB];
  status_reg[`DRV0] = status_reg_otp[`DRV0];
  status_reg[`DRV1] =  status_reg_otp[`DRV1];
  status_reg[`LB1] = status_reg_otp[`LB1];
  status_reg[`LB2] = status_reg_otp[`LB2];
  status_reg[`LB3] = status_reg_otp[`LB3];
/*
  status_reg[`S10] = status_reg_otp[`S10]; //reset together   -Lydia 250730
  status_reg[`S16] = status_reg_otp[`S16];
  status_reg[`S17] = status_reg_otp[`S17];
  status_reg[`S18] = status_reg_otp[`S18];
  status_reg[`S19] = status_reg_otp[`S19];
  status_reg[`S23] = status_reg_otp[`S23]; //reset together   -Lydia 250730
  status_reg[`CL]  = status_reg_otp[`CL]; //reset together   -Lydia 250730*/

	flag_prog_page = 0;
	flag_prog_secsi_page = 0;
	flag_erase_sector = 0;
	flag_erase_half_block = 0;
  	flag_erase_block = 0;		
	flag_erase_secsi_sector = 0;
	flag_erase_bulk = 0;
	flag_power_down = 0;
	flag_power_up_exec = 0;
	flag_power_up_sig_read = 0;
	flag_write_status_reg = 0;
	flag_slow_read_reg = 1'b0;				
	flag_read_op_reg = 1'b0;      
	flag_suspend = 1'b0;          
	flag_suspend_enabled = 1'b0;
	flag_resume = 1'b0; //add missing reset -Lydia 250804
	flag_volatile_sr_write = 1'b0;
	flag_qpi_mode = 0;   
	flag_enable_reset = 0;
	flag_enable_otp = 1'b0; //add missing reset -Lydia 250725
	flag_otp = 1'b0;        //add missing reset -Lydia 250725
	flag_reset = 0;
	flag_reset_condition = 0;
	flag_set_read_param = 0;
	timing_error = 0;
	cmd_byte = 0;
	null_reg = 0;
	in_byte = 0;
	out_byte = 0;
	get_dummy_cyc = 6;//new for dummy task -Lydia 250715
	get_dummy_cyc_dtr = 8; //new for dummy task -Lydia 250715

	//add missing reset but need check from charlie -Lydia 250725
	status_reg_shadow = 0;
	byte_address = 0;
	prog_byte_address = 0;
	prog_byte_number = 0;
	read_param_reg_shadow = 0;
end
endtask


always@(read_param_reg) begin
    case(read_param_reg[6:4])
      3'b000, 3'b001, 3'b010 : begin get_dummy_cyc =  6; get_dummy_cyc_dtr =  8; end
      3'b011                 : begin get_dummy_cyc =  8; get_dummy_cyc_dtr =  8; end
      3'b100                 : begin get_dummy_cyc = 10; get_dummy_cyc_dtr = 10; end
      3'b101                 : begin get_dummy_cyc = 12; get_dummy_cyc_dtr = 12; end
      3'b110                 : begin get_dummy_cyc = 14; get_dummy_cyc_dtr = 14; end
      3'b111                 : begin get_dummy_cyc = 16; get_dummy_cyc_dtr = 16; end
      default                : begin get_dummy_cyc =  6; get_dummy_cyc_dtr =  8; end
    endcase
end


task input_byte;
output [7:0] input_data;
integer x;
begin

   if(flag_qpi_mode == 1)
      input_byte_quad(input_data);
   else
   begin	
	   
	   if(DIO_Output_Enable_reg != 1'b0)
		   DIO_Output_Enable_reg = 1'b0;
	
	   for(x = 7; x >= 0; x=x-1)
	   begin
	      get_posclk_holdn;
         input_data[x] = DIO;
      end
	   in_byte = input_data;
	end
end
endtask


task input_byte_DTR;
output [7:0] input_data;
integer x;
begin

   if(flag_qpi_mode == 1)
      input_byte_quad_DTR(input_data);  //should use quad_DTR    -Charlie 230825
   else
   begin	
	   
	   if(DIO_Output_Enable_reg != 1'b0)
		   DIO_Output_Enable_reg = 1'b0;
	
	   for(x = 7; x >= 0; x=x-2)
	   begin
	      	get_posclk_holdn;
         	input_data[x] = DIO;
	      	get_negclk_holdn;
         	input_data[x-1] = DIO;
	   end
	   in_byte = input_data;
	end
end
endtask


task input_byte_no1stclock;
output [7:0] input_data;
integer x;
begin

   if(flag_qpi_mode == 1)
      input_byte_quad_no1stclock(input_data);
   else
   begin	
      
	   if(DIO_Output_Enable_reg != 1'b0)
		   DIO_Output_Enable_reg = 1'b0;
	
	   for(x = 7; x >= 0; x=x-1)
	   begin
	      if(x != 7)
    	   	   get_posclk_holdn;
         input_data[x] = DIO;
      end
	   in_byte = input_data;
   end
end
endtask


task input_byte_dual;
output [7:0] input_data;
integer x;
begin
	
	
	if(DIO_Output_Enable_reg != 1'b0)
		DIO_Output_Enable_reg = 1'b0;
	
	
	if(DO_Output_Enable != 1'b0)
		DO_Output_Enable = 1'b0;
	
	for(x = 7; x >= 0; x=x-2)
	begin
	   get_posclk_holdn;
	   
	   input_data[x-1] = DIO;		
		input_data[x] = DO;   
   end
	in_byte = input_data;
end
endtask


task input_byte_dual_DTR;
output [7:0] input_data;
integer x;
begin
	
	
	if(DIO_Output_Enable_reg != 1'b0)
		DIO_Output_Enable_reg = 1'b0;
	
	
	if(DO_Output_Enable != 1'b0)
		DO_Output_Enable = 1'b0;
	
	for(x = 7; x >= 0; x=x-4)
	begin
	   get_posclk_holdn;
	   input_data[x-1] = DIO;		
	   input_data[x] = DO;   
	   get_negclk_holdn;
	   input_data[x-3] = DIO;		
	   input_data[x-2] = DO;   
   end
	in_byte = input_data;
end
endtask


task input_mode_dual;
output [5:0] input_data;
integer x;
begin
	
	
	if(DIO_Output_Enable_reg != 1'b0)
		DIO_Output_Enable_reg = 1'b0;
	
	
	if(DO_Output_Enable != 1'b0)
		DO_Output_Enable = 1'b0;
	
	for(x = 5; x >= 0; x=x-2)
	begin
	   get_posclk_holdn;
	   
	   input_data[x-1] = DIO;		
		input_data[x] = DO;   
   end

end
endtask


task input_byte_quad;
output [7:0] input_data;
integer x;
begin

	
	if(DIO_Output_Enable_reg != 1'b0)
		DIO_Output_Enable_reg = 1'b0;
	
	
	if(DO_Output_Enable != 1'b0)
		DO_Output_Enable = 1'b0;

	
	if(WPn_Output_Enable_reg != 1'b0)
		WPn_Output_Enable_reg = 1'b0;

	
	if(HOLDn_Output_Enable != 1'b0)
		DO_Output_Enable = 1'b0;

	for(x = 7; x >= 0; x=x-4)
	begin
	   @(posedge CLK);
		input_data[x-3] = DIO;
      		input_data[x-2] = DO;
		input_data[x-1] = WPn;
		input_data[x] = HOLDn;
   end
	in_byte = input_data;
end
endtask


task input_byte_quad_DTR;
output [7:0] input_data;
integer x;
begin

	
	if(DIO_Output_Enable_reg != 1'b0)
		DIO_Output_Enable_reg = 1'b0;
	
	
	if(DO_Output_Enable != 1'b0)
		DO_Output_Enable = 1'b0;

	
	if(WPn_Output_Enable_reg != 1'b0)
		WPn_Output_Enable_reg = 1'b0;

	
	if(HOLDn_Output_Enable != 1'b0)
		DO_Output_Enable = 1'b0;

	for(x = 7; x >= 0; x=x-8)
	begin
	   @(posedge CLK);
		input_data[x-3] = DIO;
      		input_data[x-2] = DO;
		input_data[x-1] = WPn;
		input_data[x] = HOLDn;
	   @(negedge CLK);
		input_data[x-7] = DIO;
      		input_data[x-6] = DO;
		input_data[x-5] = WPn;
		input_data[x-4] = HOLDn;
   end
	in_byte = input_data;
end
endtask


task input_byte_quad_no1stclock;
output [7:0] input_data;
integer x;
begin

	
	if(DIO_Output_Enable_reg != 1'b0)
		DIO_Output_Enable_reg = 1'b0;
	
	
	if(DO_Output_Enable != 1'b0)
		DO_Output_Enable = 1'b0;

	
	if(WPn_Output_Enable_reg != 1'b0)
		WPn_Output_Enable_reg = 1'b0;

	
	if(HOLDn_Output_Enable != 1'b0)
		DO_Output_Enable = 1'b0;

	for(x = 7; x >= 0; x=x-4)
	begin
	   if(x != 7) 
	      @(posedge CLK);
	  	input_data[x-3] = DIO;
     input_data[x-2] = DO;
		 input_data[x-1] = WPn;
		 input_data[x] = HOLDn;
  end
	in_byte = input_data;
end
endtask



task output_byte;
input [7:0] output_data;
integer x;
begin
   
   if(flag_qpi_mode == 1)
      output_byte_quad(output_data);
   else
   begin
      out_byte = output_data;
      for(x = 7; x >= 0; x=x-1)
	   begin
	      get_negclk_holdn;
		   
		   if(DO_Output_Enable == 1'b0)					
			   DO_Output_Enable = 1'b1;
         #tCLQV DO_Reg = output_data[x];
	   end
   end
end
endtask


task output_byte_DTR;
input [7:0] output_data;
integer x;
begin
   
   if(flag_qpi_mode == 1)
      output_byte_quad_DTR(output_data); //fix DTR task   -Lydia  250711
   else
   begin
      out_byte = output_data;
	   for(x = 7; x >= 0; x=x-2)
	   begin
	      get_negclk_holdn;
		   
		   if(DO_Output_Enable == 1'b0)					
			   DO_Output_Enable = 1'b1;
         	#tCLQV DO_Reg = output_data[x];
	      get_posclk_holdn;
		   
		   if(DO_Output_Enable == 1'b0)					
			   DO_Output_Enable = 1'b1;
         	#tCLQV DO_Reg = output_data[x-1];
	   end
   end
end
endtask


task output_byte_dual;
input [7:0] output_data;
integer x;
begin
	out_byte = output_data;
	for(x = 7; x >= 0; x=x-2)
	begin
	   get_negclk_holdn;
	   
		if(DO_Output_Enable == 1'b0)					
			DO_Output_Enable = 1'b1;
		if(DIO_Output_Enable_reg == 1'b0)
			DIO_Output_Enable_reg = 1'b1;
	
		#tCLQV ;
		DIO_Reg = output_data[x-1];
     	DO_Reg = output_data[x];
	end
end
endtask


task output_byte_dual_DTR;
input [7:0] output_data;
integer x;
begin
	out_byte = output_data;
	for(x = 7; x >= 0; x=x-4)
	begin
	   get_negclk_holdn;
	   
		if(DO_Output_Enable == 1'b0)					
			DO_Output_Enable = 1'b1;
		if(DIO_Output_Enable_reg == 1'b0)
			DIO_Output_Enable_reg = 1'b1;
	
		#tCLQV ;
		DIO_Reg = output_data[x-1];
     		DO_Reg = output_data[x];
	   
	   get_posclk_holdn;
	   
		if(DO_Output_Enable == 1'b0)					
			DO_Output_Enable = 1'b1;
		if(DIO_Output_Enable_reg == 1'b0)
			DIO_Output_Enable_reg = 1'b1;
	
		#tCLQV ;
		DIO_Reg = output_data[x-3];
     		DO_Reg = output_data[x-2];
	end
end
endtask


task output_byte_quad;
input [7:0] output_data;
integer x;
begin
	out_byte = output_data;
	for(x = 7; x >= 0; x=x-4)
	begin
		@(negedge CLK);
		if(DO_Output_Enable == 1'b0)					
			DO_Output_Enable = 1'b1;
		if(DIO_Output_Enable_reg == 1'b0)
			DIO_Output_Enable_reg = 1'b1;
		if(WPn_Output_Enable_reg == 1'b0)
			WPn_Output_Enable_reg = 1'b1;
		if(HOLDn_Output_Enable == 1'b0)
			HOLDn_Output_Enable = 1'b1;
	
		#tCLQV;
		DIO_Reg = output_data[x-3];
		DO_Reg = output_data[x-2];
   	WPn_Reg = output_data[x-1];
   	HOLDn_Reg = output_data[x];
	end
end
endtask


task output_byte_quad_DTR;
input [7:0] output_data;
integer x;
begin
	out_byte = output_data;
	for(x = 7; x >= 0; x=x-8)
	begin
		@(negedge CLK);
		if(DO_Output_Enable == 1'b0)					
			DO_Output_Enable = 1'b1;
		if(DIO_Output_Enable_reg == 1'b0)
			DIO_Output_Enable_reg = 1'b1;
		if(WPn_Output_Enable_reg == 1'b0)
			WPn_Output_Enable_reg = 1'b1;
		if(HOLDn_Output_Enable == 1'b0)
			HOLDn_Output_Enable = 1'b1;
	
		#tCLQV;
		DIO_Reg = output_data[x-3];
		DO_Reg = output_data[x-2];
   		WPn_Reg = output_data[x-1];
   		HOLDn_Reg = output_data[x];
		
		@(posedge CLK);
		if(DO_Output_Enable == 1'b0)					
			DO_Output_Enable = 1'b1;
		if(DIO_Output_Enable_reg == 1'b0)
			DIO_Output_Enable_reg = 1'b1;
		if(WPn_Output_Enable_reg == 1'b0)
			WPn_Output_Enable_reg = 1'b1;
		if(HOLDn_Output_Enable == 1'b0)
			HOLDn_Output_Enable = 1'b1;
	
		#tCLQV;
		DIO_Reg = output_data[x-7];
		DO_Reg = output_data[x-6];
   		WPn_Reg = output_data[x-5];
   		HOLDn_Reg = output_data[x-4];
	end
end
endtask


task get_negclk_holdn;
begin

   if(status_reg[`QE])              
	   @(negedge CLK);               
	else
	   @(negedge (CLK & HOLDn));     

end
endtask


task get_posclk_holdn;
begin

   if(status_reg[`QE])              
	   @(posedge CLK);               
	else
	   @(posedge (CLK & HOLDn));     

end
endtask


task wait_reset_suspend;
input [31:0] delay;
integer waitx;
integer num_iterations;
begin
    






      waitx = 0;
      
      if(delay >= tReset_Suspend_Max)
      begin
        num_iterations = delay / tReset_Suspend_Max;
      		for(waitx = 0; waitx < num_iterations; waitx=waitx+1)    
      		begin
	   			if(flag_reset_condition)                                          
	   			   waitx = num_iterations;                           
        else
        begin
		  		   wait(!flag_suspend_enabled || flag_reset_condition);
	   			   #tReset_Suspend_Max;
	   			end
		  	end
		  end

      num_iterations = delay % tReset_Suspend_Max;
    		for(waitx = 0; waitx < num_iterations; waitx=waitx+1)    
    		begin
    		   if(flag_reset_condition)                                  
    		      waitx = num_iterations;
	      else
	      begin 
		      wait(!flag_suspend_enabled || flag_reset_condition);   
          #1;
		   end
  	   end
end
endtask


task wait_reset;
input [31:0] delay;
integer waitx;
integer num_iterations;
begin





      waitx = 0;
      
      if(delay >= tReset_Suspend_Max)
      begin
        num_iterations = delay / tReset_Suspend_Max;
      		for(waitx = 0; waitx < num_iterations; waitx=waitx+1)    
      		begin
	   			if(flag_reset_condition)                                 
	   			   waitx = num_iterations;                           
        else
	   			   #tReset_Suspend_Max;                              
   	  	 end
		  end

      num_iterations = delay % tReset_Suspend_Max;
    		for(waitx = 0; waitx < num_iterations; waitx=waitx+1)    
    		begin
    		   if(flag_reset_condition)                          
    		      waitx = num_iterations;
	      else
            #1;
  	   end
end
endtask


//new write_protect function  -Lydia 250714
//protect_pa_lower
always@( status_reg[`SEC] or status_reg[`TB] or sr_BP ) 
begin
    
    //Sector Protect
    if( status_reg[`SEC] == 1'b1 ) 
    begin
	if( status_reg[`TB] === 1'b0 ) 
	begin
	    if(sr_BP == 3'd7) 
		protect_pa_lower = {WIDTH_PA_ADDR{1'b0}};
	    else if(sr_BP >= 3'd4) 
		protect_pa_lower = 2 ** WIDTH_PA_ADDR - ( SECTORSIZE * 8 );
	    else
		protect_pa_lower = 2 ** WIDTH_PA_ADDR - ( SECTORSIZE * ( 2 ** ( sr_BP - 1 ) ) );
	end
	else
	    protect_pa_lower =  {WIDTH_PA_ADDR{1'b0}};
    end
    
    //Block Protect
    else if((status_reg[`TB] === 1'b0) && (sr_BP >= 3'd1) && (sr_BP <= TABLE_UPPER_LIMIT))
	protect_pa_lower = 2 ** WIDTH_PA_ADDR - 2 ** ( ( sr_BP + TABLE_SHIFT1 ) + 15 );
    else
	protect_pa_lower = {WIDTH_PA_ADDR{1'b0}};
end

//protect_pa_upper
always@( status_reg[`SEC] or status_reg[`TB] or sr_BP ) 
begin
    if( sr_BP === 3'd0 )
	protect_pa_upper = {WIDTH_PA_ADDR{1'b0}};
    
    //Sector protect
    else if( status_reg[`SEC] == 1'b1 ) 
    begin
	if( status_reg[`TB] === 1'b1 ) 
	begin
	    if( sr_BP == 3'd7 ) 
		protect_pa_upper = {WIDTH_PA_ADDR{1'b1}};
	    else if( sr_BP >= 3'd4 )
		protect_pa_upper = SECTORSIZE * ( 2 ** (4     - 1) ) - 1;
	    else
		protect_pa_upper = SECTORSIZE * ( 2 ** (sr_BP - 1) ) - 1;
	end
	else
	    protect_pa_upper = {WIDTH_PA_ADDR{1'b1}};
    end

    //block protect
    else if( (status_reg[`TB] === 1'b1) && (sr_BP >= 3'd1) && (sr_BP <= TABLE_UPPER_LIMIT) )
	protect_pa_upper = 2 ** ( ( sr_BP + TABLE_SHIFT2 ) + 15 ) - 1;
    else
	protect_pa_upper = {WIDTH_PA_ADDR{1'b1}};
end


//new write_protected -Lydia 250709
function write_protected;
input [31:0] byte_address;
begin
    if( protect_pa_upper == 0 || ( byte_address[WIDTH_PA_ADDR - 1:0] < protect_pa_lower || byte_address[WIDTH_PA_ADDR - 1:0] > protect_pa_upper ) )
	write_protected = ( status_reg[`CMPB] ) ? 1'b1 : 1'b0;
    else
	write_protected = ( status_reg[`CMPB] ) ? 1'b0 : 1'b1;
end
endfunction


function is_qpi;
input [7:0] cmd_byte;
begin
    if(flag_qpi_mode == 1)
    begin
	case (cmd_byte)				         

      `CMD_WRITE_ENABLE,`CMD_WRITE_ENABLE_VSR, `CMD_WRITE_DISABLE, `CMD_READ_STATUS, `CMD_READ_STATUS2, `CMD_READ_STATUS3, 
      `CMD_WRITE_STATUS, `CMD_WRITE_STATUS2, `CMD_WRITE_STATUS3, `CMD_PAGE_PROGRAM, 
      `CMD_SECTOR_ERASE,`CMD_HALF_BLOCK_ERASE, `CMD_BLOCK_ERASE, `CMD_BULK_ERASE, `CMD_BULK_ERASE2,
      `CMD_SUSPEND, `CMD_RESUME, `CMD_DEEP_POWERDOWN, `CMD_SET_READ_PARAM, `CMD_READ_DATA_FAST,
      `CMD_READ_DATA_FAST_WRAP, `CMD_READ_DATA_FAST_QUAD_IO, `CMD_READ_SIGNATURE, `CMD_READ_ID, `CMD_READ_JEDEC_ID,
      `CMD_READ_UNIQUE_ID, `CMD_DISABLE_QPI, `CMD_ENABLE_RESET, `CMD_CHIP_RESET,
      `ifdef IM
          `CMD_READ_DATA_FAST_DTR_WRAP, `CMD_READ_DATA_FAST_DTR, `CMD_READ_DATA_FAST_QUAD_IO_DTR,
      `endif
      `CMD_READ_SFDP , `CMD_SREG_READ:
       begin
         is_qpi = 1;
       end
  
       default :
	    begin
		   is_qpi = 0;
		   $display("Invalid Opcode for QPI mode. (%0h)",cmd_byte);
	    end
	    endcase 
   end
   else
      is_qpi = 1;

end
endfunction


task read_page;
input [1:0] fast_read;                         
input [1:0] mem_read;                          
input four_byte_address;
integer x;

begin
    if(!status_reg[`WIP])
    begin
    
	input_byte(byte_address[23:16]);	
	input_byte(byte_address[15:8]);
	input_byte(byte_address[7:0]);

	byte_address = byte_address & ADDRESS_MASK;

	if(fast_read)
	begin
	    if(flag_qpi_mode == 1)
		input_dummy(get_dummy_cyc); //new dummy task -Lydia 250716
	    else 
		input_byte(null_reg);
   	end
   	
   	if(mem_read == 2 || mem_read == 1)    
	    input_byte(null_reg);
	if(mem_read == 2 && flag_qpi_mode)
	begin   
	    input_byte(null_reg);
	    input_byte(null_reg);
	    input_byte(null_reg);
	end
		
	forever
	begin
	    if(mem_read == 1) 
	    begin
		case(byte_address[23:8])
		    16'h10 :  
			output_byte(secsi[byte_address[7:0]]);             
           	    16'h20 :
			output_byte(secsi[byte_address[7:0]+PAGESIZE]);                       
           	    16'h30 :
       			output_byte(secsi[byte_address[7:0]+(2*PAGESIZE)]);                       
           	    default :
           	    begin
			$display("Invalid Security Page Address (%x)",byte_address);
             		$stop;
           	    end
           	endcase  
            end
	    
	    else if(mem_read == 2) 
	    begin
		if(byte_address[23:8] == 0)    
                begin
		    output_byte(sfdp[byte_address[7:0]]);
                end
		else
		begin
		    $display("Invalid SFDP Page Address (%x)", byte_address);
		    $stop;
                end		     
	    end
	    
	    else if(mem_read == 0)   
	    begin
		byte_address = byte_address & ADDRESS_MASK;
		if(fast_read == 2)
		    output_byte_dual(memory[byte_address]);
      		else if(fast_read == 3)
		    output_byte_quad(memory[byte_address]);
      		else
		    output_byte(memory[byte_address]);
  	    end
              
	    if(mem_read)
		byte_address[7:0] = byte_address[7:0] + 1;
	    else
       		byte_address = byte_address + 1;
   	end
    end
end
endtask



task read_page_dualio;
input four_byte_address;  
begin

	if(!status_reg[`WIP])
	begin

	  

		input_byte_dual(byte_address[23:16]);	
		input_byte_dual(byte_address[15:8]);
		input_byte_dual(byte_address[7:0]);
		input_mode_dual(mode_reg[7:2]);         
	  get_posclk_holdn;                       
      	
		forever
		begin
			byte_address = byte_address & ADDRESS_MASK;
                        output_byte_dual(memory[byte_address]);
			byte_address = byte_address + 1;
		end
	end
end
endtask


task read_page_quadio;
input [7:0] cmd;
input four_byte_address;
integer x;

begin
    input_byte_quad(byte_address[23:16]);
    input_byte_quad(byte_address[15:8]);
    input_byte_quad(byte_address[7:0]);
    
    if(!status_reg[`WIP])
    begin
	case (cmd)
	    `CMD_READ_DATA_FAST_QUAD_IO:
            begin
		input_byte_quad(mode_reg[7:0]);
		input_dummy(get_dummy_cyc - 2); //-2 for mode_reg  -Lydia 250715

                if(mode_reg[4] == 1)                                   
		    mode_reg = 8'h00;
            end

	    `CMD_READ_DATA_FAST_WRAP :
	    begin
		input_dummy(get_dummy_cyc);//wait dummy -Lydia 250715
	    end
	endcase	   
	
	forever
	begin
	    byte_address = byte_address & ADDRESS_MASK;
	    output_byte_quad(memory[byte_address]);
	    if(cmd == `CMD_READ_DATA_FAST_WRAP)
	    begin
		case ({read_param_reg[1],read_param_reg[0]})		    
		    2'b00 :
			byte_address[2:0] = byte_address[2:0] + 1;
		    2'b01 :
			byte_address[3:0] = byte_address[3:0] + 1;
		    2'b10 :
			byte_address[4:0] = byte_address[4:0] + 1;
		    2'b11 :
			byte_address[5:0] = byte_address[5:0] + 1;
		endcase
	    end
	    else
		if(!wrap_reg[4] && (cmd == `CMD_READ_DATA_FAST_QUAD_IO))
		begin
		    case ({wrap_reg[6],wrap_reg[5]})		    
			2'b00 :
			    byte_address[2:0] = byte_address[2:0] + 1;
			2'b01 :
			    byte_address[3:0] = byte_address[3:0] + 1;
			2'b10 :
			    byte_address[4:0] = byte_address[4:0] + 1;
			2'b11 :
			    byte_address[5:0] = byte_address[5:0] + 1;
		    endcase
		end
		else
		    byte_address = byte_address + 1;
			
	end
    end
end
endtask



task write_page;
input quadio;
input four_byte_address;
integer x;
integer address;

begin
	if(!status_reg[`WIP])
	begin


		input_byte(prog_byte_address[23:16]);
		input_byte(prog_byte_address[15:8]);
		input_byte(prog_byte_address[7:0]);
		prog_byte_address = prog_byte_address & ADDRESS_MASK; //add ADDRESS_MASK  -Lydia  250710
		if(!write_protected(prog_byte_address))
		   fill_page_latch(quadio,prog_byte_address,0);
	end
end
endtask


task fill_page_latch;

input 		quadio;
input   [31:0] 	prog_address;
input 		flag_secsi;
integer 	x;
integer 	address;

begin
	prog_byte_number = 0;
	
  	if(flag_secsi)
  	begin
		address = (prog_address >> 4) - 31'h100;
		address[7:0] = 0;
  	end
  	else
  	begin
		address = prog_address;
   		address[7:0] = 0;
	end
	
	for(x = 0; x < PAGESIZE; x=x+1)
	   page_latch[x] = flag_secsi ? secsi[address+x] : memory[address+x];
	
	forever
	begin
	   	if(quadio)
			input_byte_quad(temp);
		else
			input_byte(temp);
		
		page_latch[prog_address[7:0]] = temp;

		//add counter limit  -Lydia 250710
		if(!(prog_byte_number==256))
		    prog_byte_number = prog_byte_number + 1;
		else
		    prog_byte_number = 256;
		
		if(flag_secsi)
		  	flag_prog_secsi_page = 1;
		else
  		  	flag_prog_page = 1;
		
		prog_address[7:0] = prog_address[7:0] + 1;
	end
end
endtask






task dump_mem;
integer x;
integer file;
begin
  
  file = $fopen(`MEM_FILENAME);

  
  	
	for(x = 0; x < (NUM_PAGES * PAGESIZE); x=x+1)
	begin
	  if(x % 16)
	     $fwrite(file,"%h ", memory[x]);
	  else
	     $fwrite(file,"\n%h ", memory[x]);	    
  end		   
  $fclose(file);
  
end
endtask





task dump_mem_page;

integer r, x;
integer file;

begin


	
	file = $fopen(`MEM_FILENAME, "r+");

	r = $fseek(file, 3*(prog_byte_address[23:4]*16+prog_byte_address[3:0])+2*prog_byte_address[23:4], 0);
	
	for(x = prog_byte_address; x < (prog_byte_address + prog_byte_number); x=x+1)
	begin
		$fwrite(file,"%h ", memory[x]);
		if (!((x+1)%16))
			$fwrite(file,"\n");
  	end
	
	$fclose(file);
  
end
endtask





task dump_erase_page;
input [19:0] page_number;
integer r, x;
integer file;
begin
  
  file = $fopen(`MEM_FILENAME, "r+");
  r = $fseek(file, page_number*3*PAGESIZE+32*page_number, 0);
	for(x = 0; x < PAGESIZE; x=x+1)
	begin
	     $fwrite(file,"ff ");
	  if (!((x+1)%16))
	     $fwrite(file,"\n");
  end
  $fclose(file);
  
end
endtask


//task wait dummy cycle   -Lydia  250715
task input_dummy;
input [4:0] input_dummy_cyc;
integer x;
begin
    if( DIO_Output_Enable_reg != 1'b0 )
	DIO_Output_Enable_reg = 1'b0;
    if( DO_Output_Enable != 1'b0 )
	DO_Output_Enable = 1'b0;
    if( WPn_Output_Enable_reg != 1'b0 )
	WPn_Output_Enable_reg = 1'b0;
    if( HOLDn_Output_Enable != 1'b0 )
	DO_Output_Enable = 1'b0;
    
    for( x = 0; x < input_dummy_cyc; x=x+1 )
	get_posclk_holdn;
end
endtask

always @(posedge flag_set_read_param)
begin :set_read_param
	@(posedge CSn);
	if(flag_set_read_param == 1)
	begin
       if(flag_qpi_mode)begin
	       read_param_reg = read_param_reg_shadow;
       end
       else begin
	       read_param_reg[6:4] = read_param_reg_shadow[6:4];
       end
	end
   flag_set_read_param = 0;	
end
 				
 				
 				

always @(posedge flag_reset)

begin :reset

	@(posedge CSn);
	if((flag_reset == 1) && (flag_write_status_reg == 0))  
	begin
	status_reg[`WIP] = 1;
      flag_reset_condition = 1;
      #tRES1;                     	    
      chip_reset;

	end
	flag_reset = 0;
end




always @(posedge flag_power_up_exec)

begin :power_up

	@(posedge CSn);
	if(flag_power_up_exec == 1)
	begin
			#tRES1;

    flag_power_down = 0;
		flag_power_up_exec = 0;
		flag_power_up_sig_read = 0;
		flag_suspend = 0;
	end
end


always @(posedge flag_power_down)

begin :power_down

	@(posedge CSn);
	if(flag_power_down == 1)
	begin
		#tDP;
	end
end



always @(posedge flag_suspend)		

begin :erase_suspend

	@(posedge CSn);					              
	if(flag_suspend == 1)
	begin
	   status_reg[`SUS] = 1;
      wait_reset(tSUS);
      flag_suspend_enabled = 1'b1;
      status_reg[`WIP] = 0;
      status_reg[`WEL] = 0;
      
   end
end


always @(posedge flag_resume)		

begin :erase_resume

	@(posedge CSn);					              
	if(flag_resume == 1)
	begin
	   status_reg[`SUS] = 0;
	   flag_suspend_enabled = 1'b0;
	   flag_suspend = 1'b0;
	   flag_resume = 1'b0;
	   status_reg[`WEL] = 1;
	   status_reg[`WIP] = 1;
	   
   end
end


always @(posedge flag_erase_sector)		
									                   
begin :erase_sector
integer x;

	@(posedge CSn);					               
	if(flag_erase_sector == 1)
	begin
		status_reg[`WIP] = 1;

    wait_reset_suspend(tSE);	
 	  
		for(x = 0; x < SECTORSIZE; x=x+1)
			memory[(byte_address[23:12] * SECTORSIZE) + x] = 8'hff;

		for(x = byte_address[23:12]; x < 16; x=x+1)
			dump_erase_page(x);

		status_reg[`WIP] = 0;
		status_reg[`WEL] = 0;
	end
	flag_erase_sector = 0;
end


always @(posedge flag_erase_secsi_sector)		
									                         
begin :erase_secsi_sector
integer x;

	@(posedge CSn);					               
	if(flag_erase_secsi_sector == 1)
	begin
		status_reg[`WIP] = 1;

    case(byte_address[23:8])
      16'h10 :  
      begin
        wait_reset_suspend(tSE);      
      		for(x = 0; x < PAGESIZE; x=x+1)
        			secsi[x] = 8'hff;
   			end     
      16'h20 :
      begin
        wait_reset_suspend(tSE);      
      		for(x = 0; x < PAGESIZE; x=x+1)
        			secsi[x+PAGESIZE] = 8'hff;      
   			end
      16'h30 :
      begin
        wait_reset_suspend(tSE);      
      		for(x = 0; x < PAGESIZE; x=x+1)
        			secsi[x+(PAGESIZE * 2)] = 8'hff;
   			end
      default :
      begin
        $display("Invalid Security Page Erase Address (%x)",byte_address);
        $stop;
      end
    endcase  

		status_reg[`WIP] = 0;
		status_reg[`WEL] = 0;
	end
	flag_erase_secsi_sector = 0;
end




always @(posedge flag_erase_block)		      
								                  
begin :erase_block
integer x;

	@(posedge CSn);					                   
	if(flag_erase_block == 1)
	begin
		status_reg[`WIP] = 1;
		
		wait_reset_suspend(tBE2);

		for(x = 0; x < BLOCKSIZE; x=x+1)
			memory[(byte_address[23:16] * BLOCKSIZE) + x] = 8'hff;

    status_reg[`WIP] = 0;
		status_reg[`WEL] = 0;
	end
	flag_erase_block = 0;
end


always @(posedge flag_erase_half_block)		
						      		               
begin :erase_half_block
integer x;

	@(posedge CSn);					                  
	if(flag_erase_half_block == 1)
	begin
		status_reg[`WIP] = 1;

      wait_reset_suspend(tBE1);

		for(x = 0; x < HALFBLOCKSIZE; x=x+1)
			memory[(byte_address[23:15] * HALFBLOCKSIZE) + x] = 8'hff;

		status_reg[`WIP] = 0;
		status_reg[`WEL] = 0;
	end
	flag_erase_half_block = 0;
end




always @(posedge flag_erase_bulk)	
                                  
begin :erase_bulk
integer x;

	@(posedge CSn);			             
	if(flag_erase_bulk == 1)
	begin
	    status_reg[`WIP] = 1;
	    //add parameter for diff density  -Lydia 250709
		for(x = 0; x < TCE_PAR; x=x+1)  //change to parameter for diff density  -Lydia 250709
			wait_reset(tCE_unit);

		for(x = 0; x < PAGESIZE * NUM_PAGES; x=x+1)
		    memory[x] = 8'hff;

		status_reg[`WIP] = 0;
		status_reg[`WEL] = 0;
	end
	flag_erase_bulk = 0;

end



always @(posedge flag_prog_page)			
									    	            
begin :program_to_page
reg [31:0] x;                         

	@(posedge CSn);						            
	begin
    		status_reg[`WIP] = 1;

		if((prog_byte_address[7:0]+prog_byte_number[8:0]) > PAGESIZE)
      		begin
      			prog_byte_address[7:0] = 0;
      			prog_byte_number = 256;
      		end
      		
      		for(x = prog_byte_address; x < (prog_byte_address+prog_byte_number[8:0]); x=x+1)    
      		begin
          		memory[x] = page_latch[x[7:0]] & memory[x];
        		wait_reset_suspend(tPP / PAGESIZE);
    		end

		dump_mem_page;

		status_reg[`WIP] = 0;
    		status_reg[`WEL] = 0;
	end
	flag_prog_page = 0;
end


always @(posedge flag_prog_secsi_page)				
									    	                   
begin :program_to_secsi_page
integer x;                                

	@(posedge CSn);					       	            
	begin
    		status_reg[`WIP] = 1;
      prog_byte_address[7:0] = 0;
      
      case(prog_byte_address[23:8])
        16'h10 :  
        begin
           for(x = 0; x < PAGESIZE; x=x+1)    
           begin
              secsi[x] = page_latch[x] & secsi[x];
            		wait_reset_suspend(tPP / PAGESIZE);
         		end
     			end     
        16'h20 :
        begin
           for(x = 0; x < PAGESIZE; x=x+1)    
           begin
              secsi[x+PAGESIZE] = page_latch[x] & secsi[x+PAGESIZE];
            		wait_reset_suspend(tPP / PAGESIZE);
         		end
     			end     
        16'h30 :
        begin
           for(x = 0; x < PAGESIZE; x=x+1)    
           begin
              secsi[x+(PAGESIZE*2)] = page_latch[x] & secsi[x+(PAGESIZE*2)];
            		wait_reset_suspend(tPP / PAGESIZE);
         		end
     			end     
        default :
        begin
          $display("Invalid Security Page Program Address (%x)",prog_byte_address);
          $stop;
        end
      endcase  

		status_reg[`WIP] = 0;
		status_reg[`WEL] = 0;
	end
	flag_prog_secsi_page = 0;
end





always @(posedge flag_write_status_reg)	    		        
	                                  									         
begin :write_status_reg

    @(posedge CSn);						
    if(flag_write_status_reg == 1)
    begin
	status_reg[`WIP] = 1;
	status_reg[`QE] = (flag_qpi_mode) ? status_reg[`QE] : status_reg_shadow[`QE]; //in qpi mode cant change QE Lydia 250711
	status_reg[`SRL] = status_reg_shadow[`SRL];
	status_reg[`SRP] = status_reg_shadow[`SRP];
	status_reg[`BP0] = status_reg_shadow[`BP0];
	status_reg[`BP1] = status_reg_shadow[`BP1];
	status_reg[`BP2] = status_reg_shadow[`BP2];
	status_reg[`SEC] = status_reg_shadow[`SEC];
	status_reg[`TB] = status_reg_shadow[`TB];
	status_reg[`CMPB] = status_reg_shadow[`CMPB];
	status_reg[`DRV0] = status_reg_shadow[`DRV0];
	status_reg[`DRV1] =  status_reg_shadow[`DRV1];
	status_reg[`CL]   =  status_reg_shadow[`CL];
	  
	status_reg[`S23] = status_reg[`S23] | status_reg_shadow[`S23];
     	status_reg[`S10] = status_reg[`S10] | status_reg_shadow[`S10];


	  
        status_reg[`LB1] = status_reg[`LB1] | status_reg_shadow[`LB1];
        status_reg[`LB2] = status_reg[`LB2] | status_reg_shadow[`LB2];
        status_reg[`LB3] = status_reg[`LB3] | status_reg_shadow[`LB3];

	if(!flag_volatile_sr_write)
	begin
	    if(flag_otp)
		status_reg_otp[`SRL] = status_reg_shadow[`SRL];

`ifdef IM
	    status_reg_otp[`QE] = status_reg_shadow[`QE];
`elsif IG
	    status_reg_otp[`QE] = 1'b1;
`endif

  	    status_reg_otp[`SRP] = status_reg_shadow[`SRP];
  	    status_reg_otp[`BP0] = status_reg_shadow[`BP0];
  	    status_reg_otp[`BP1] = status_reg_shadow[`BP1];
	    status_reg_otp[`BP2] = status_reg_shadow[`BP2];
	    status_reg_otp[`TB] = status_reg_shadow[`TB];
	    status_reg_otp[`CMPB] = status_reg_shadow[`CMPB];
	    status_reg_otp[`SEC] =  status_reg_shadow[`SEC];
	    status_reg_otp[`CL] =  status_reg_shadow[`CL];

	    status_reg_otp[`DRV0] = status_reg_shadow[`DRV0];
	    status_reg_otp[`DRV1] =  status_reg_shadow[`DRV1];


            status_reg_otp[`S23] = status_reg[`S23] | status_reg_shadow[`S23];
            status_reg_otp[`S10] = status_reg[`S10] | status_reg_shadow[`S10];
	      
            status_reg_otp[`LB1] = status_reg[`LB1] | status_reg_shadow[`LB1];
            status_reg_otp[`LB2] = status_reg[`LB2] | status_reg_shadow[`LB2];
            status_reg_otp[`LB3] = status_reg[`LB3] | status_reg_shadow[`LB3];
	end   
      
	if(status_reg[`QE] == 0)
	    flag_qpi_mode = 0;
         
  	if(status_reg[`WEL])
	    wait_reset(tW);
	   
	status_reg[`WIP] = 0;
	status_reg[`WEL] = 0;
	flag_volatile_sr_write = 0;
	flag_write_status_reg = 0;
    end
end


endmodule 
